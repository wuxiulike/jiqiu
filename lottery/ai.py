import json
import re
from urllib.parse import urlparse
import requests

SYSTEM_PROMPT = '''你是双色球数据分析助手。只依据输入的真实开奖和走势统计进行分析，不得编造开奖、回测结果或来源。若有程序算法初选号码，必须逐注参考这些号码和提供的历史走势，判断、保留或调整，说明每注调整依据；不强求一定改变。输出的每注须按原顺序与初选一一对应，不要调换各注顺序。分别说明历史事实、选号依据和局限；未知遗漏不能当作具体数值。若开奖独立且等概率，历史频率、遗漏和模型不能证明下期更可能出现；不要声称提高中奖率、保证中奖或鼓励追加投注。给出指定数量的下一期娱乐性候选号码，每注恰好6个不重复的1到33红球和1个1到16蓝球。请只输出 JSON 对象，analysis 放在最前，格式为 {"analysis":"中文历史分析与局限", "tickets":[{"red":[1,2,3,4,5,6],"blue":7,"reason":"该注选择依据"}]}，不要输出其他文本。'''


def normalize_base_url(base):
    base = base.strip().rstrip('/')
    parsed = urlparse(base)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError('Base URL 必须是有效的 HTTP(S) 地址')
    return base if base.endswith('/chat/completions') else base + '/chat/completions'


def chat(base, model, api_key, summary, post=requests.post):
    if not model.strip() or not api_key.strip():
        raise ValueError('请填写模型名称和 API Key')
    response = post(normalize_base_url(base), headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
                    json={'model': model.strip(), 'messages': [{'role': 'system', 'content': SYSTEM_PROMPT},
                          {'role': 'user', 'content': json.dumps(summary, ensure_ascii=False)}]}, timeout=90)
    response.raise_for_status()
    try:
        result = response.json()['choices'][0]['message']['content']
        if not isinstance(result, str) or not result.strip():
            raise ValueError('空内容')
        return result
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ValueError('模型返回的数据格式无效或内容为空') from exc


def _analysis_fragment(content):
    match = re.search(r'"analysis"\s*:\s*"', content)
    if not match:
        return ''
    start = match.end()
    escaped = False
    end = start
    for i in range(start, len(content)):
        char = content[i]
        if char == '"' and not escaped:
            break
        end = i + 1
        if char == '\\':
            escaped = not escaped
        else:
            escaped = False
    raw = content[start:end]
    while raw:
        try:
            return json.loads('"' + raw + '"')
        except json.JSONDecodeError:
            raw = raw[:-1]
    return ''


def chat_stream(base, model, api_key, summary, progress, post=requests.post):
    if not model.strip() or not api_key.strip():
        raise ValueError('请先在模型设置中填写模型名称和 API Key')
    response = post(normalize_base_url(base), headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
                    json={'model': model.strip(), 'stream': True,
                          'messages': [{'role': 'system', 'content': SYSTEM_PROMPT},
                                       {'role': 'user', 'content': json.dumps(summary, ensure_ascii=False)}]},
                    timeout=(15, 90), stream=True)
    response.encoding = 'utf-8'
    content = ''
    shown = ''
    complete = False
    try:
        response.raise_for_status()
        for line in response.iter_lines(decode_unicode=True):
            if isinstance(line, bytes):
                line = line.decode('utf-8')
            if not line or not line.startswith('data:'):
                continue
            data = line[5:].strip()
            if data == '[DONE]':
                complete = True
                break
            try:
                event = json.loads(data)
                choices = event.get('choices', [])
                if not choices:
                    if 'error' in event:
                        raise ValueError('模型服务返回流式错误')
                    continue
                choice = choices[0]
                if choice.get('finish_reason') == 'length':
                    raise ValueError('模型输出被截断，请重试或调整服务端输出长度')
                if choice.get('finish_reason') not in (None, 'stop'):
                    raise ValueError('模型未正常完成输出，请重试')
                if choice.get('finish_reason') == 'stop':
                    complete = True
                part = choice.get('delta', {}).get('content') or ''
                if not isinstance(part, str):
                    raise ValueError('模型流式响应格式无效')
                content += part
                fragment = _analysis_fragment(content)
                if fragment and fragment != shown:
                    progress(fragment)
                    shown = fragment
            except (KeyError, TypeError, json.JSONDecodeError) as exc:
                raise ValueError('模型流式响应格式无效') from exc
        if not complete or not content:
            raise ValueError('模型响应未完整结束，请重试')
        return content
    finally:
        response.close()


def parse_prediction(text, count):
    text = text.strip()
    if text.startswith('```') and text.endswith('```'):
        text = text.split('\n', 1)[1].rsplit('```', 1)[0].strip() if '\n' in text else text
    try:
        data = json.loads(text)
        tickets = data['tickets']
        if not isinstance(data['analysis'], str) or not data['analysis'].strip() or not isinstance(tickets, list) or len(tickets) != count:
            raise ValueError('分析内容或注数无效')
        for ticket in tickets:
            red, blue = ticket['red'], ticket['blue']
            if (not isinstance(red, list) or len(red) != 6 or any(type(n) is not int or not 1 <= n <= 33 for n in red)
                or len(set(red)) != 6 or type(blue) is not int or not 1 <= blue <= 16
                or not isinstance(ticket.get('reason'), str) or not ticket['reason'].strip()):
                raise ValueError('候选号码或说明无效')
            ticket['red'] = sorted(red)
        return data
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError('模型返回内容或号码不符合要求') from exc


def prediction_input(draws, window, count, algorithm=None):
    from lottery.trends import make_summary
    result = make_summary(draws, window)
    result['候选注数'] = count
    if algorithm:
        result['程序算法结果'] = algorithm
    return result
