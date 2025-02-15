import gradio as gr
import regex as re
import unicodedata

from modules import script_callbacks, shared
import modules.scripts as scripts

'''
Formatting settings
'''
SPACE_COMMAS = True
BRACKET2WEIGHT = True
SPACE2UNDERSCORE = False

'''
Regex stuff
'''
brackets_opening = '([{<'
brackets_closing = ')]}>'

re_tokenize = re.compile(r'\s*,\s*')
re_comma_spacing = re.compile(r',+')
re_brackets_fix_whitespace = re.compile(r'([\(\[{<])\s*|\s*([\)\]}>}])')
re_opposing_brackets = re.compile(r'([)\]}>])([([{<])')
re_networks = re.compile(r'<.+?>')
re_bracket_open = re.compile(r'[(\[]')
re_brackets_open = re.compile(r'\(+|\[+')
re_brackets_closing = re.compile(r'\)+|\]+')
re_colon_spacing = re.compile(r'\s*(:)\s*')
re_colon_spacing_composite = re.compile(r'\s*(:)\s*(?=\d*?\.?\d*?\s*?AND)')
re_colon_spacing_comp_end = re.compile(r'(?<=AND[^:]*?)(:)(?=[^:]*$)')
re_paren_weights_exist = re.compile(r'\(.*(?<!:):\d.?\d*\)+')
re_is_prompt_editing = re.compile(r'\[.*:.*\]')
re_is_prompt_alternating = re.compile(r'\[.*|.*\]')
re_is_wildcard = re.compile(r'{.*}')
re_AND = re.compile(r'(.*?)\s*(AND)\s*(.*?)')
re_pipe = re.compile(r'\s*(\|)\s*')
re_existing_weight = re.compile(r'(?<=:)(\d+.?\d*|\d*.?\d+)(?=[)\]]$)')
re_curly_brackets = re.compile(r'\{.*?\}') # 对花括号的处理

'''
References
'''
ui_prompts = []


'''
Functions
'''
def get_bracket_closing(c: str):
    return brackets_closing[brackets_opening.find(c)]


def get_bracket_opening(c: str):
    return brackets_opening[brackets_closing.find(c)]


def normalize_characters(data: str):
    return unicodedata.normalize("NFKC", data)


def tokenize(data: str) -> list:
    return re_tokenize.split(data)


def remove_whitespace_excessive(prompt: str):
    return ' '.join(prompt.split())


def align_brackets(prompt: str):
    def helper(match: re.Match):
        return match.group(1) or match.group(2)

    return re_brackets_fix_whitespace.sub(helper, prompt)


def space_AND(prompt: str):
    def helper(match: re.Match):
        return ' '.join(match.groups())

    return re_AND.sub(helper, prompt)


def align_colons(prompt: str):
    def normalize(match: re.Match):
        return match.group(1)
    
    def composite(match: re.Match):
        return ' ' + match.group(1)
    
    def composite_end(match: re.Match):
        return ' ' + match.group(1)

    ret = re_colon_spacing.sub(normalize, prompt)
    ret = re_colon_spacing_composite.sub(composite, ret)
    ret = re_colon_spacing_comp_end.sub(composite_end, ret)
    return ret


def align_commas(prompt: str):
    if not SPACE_COMMAS:
        return prompt
    
    split = re_comma_spacing.split(prompt)
    split = map(str.strip, split)
    split = filter(None, split)
    return ', '.join(split)


def extract_networks(tokens: list):
    return list(filter(lambda token: re_networks.match(token), tokens))


def remove_networks(tokens: list):
    return list(filter(lambda token : not re_networks.match(token), tokens))


def remove_mismatched_brackets(prompt: str):
    stack = []
    pos = []
    ret = ''
    
    for i, c in enumerate(prompt):
        if c in brackets_opening:
            stack.append(c)
            pos.append(i)
            ret += c
        elif c in brackets_closing:
            if not stack:
                continue
            if stack[-1] == brackets_opening[brackets_closing.index(c)]:
                stack.pop()
                pos.pop()
                ret += c
        else:
            ret += c
    
    while stack:
        bracket = stack.pop()
        p = pos.pop()
        ret = ret[:p] + ret[p+1:]
    
    return ret


def space_bracekts(prompt: str):
    def helper(match : re.Match):
        # print(' '.join(match.groups()))
        return ' '.join(match.groups())

    # print(prompt)
    return re_opposing_brackets.sub(helper, prompt)


def align_alternating(prompt:str):
    def helper(match: re.Match):
        return match.group(1)

    return re_pipe.sub(helper, prompt)


def bracket_to_weights(prompt: str):
    """
    when scanning, we need a way to ignore prompt editing, composable, and alternating
    we still need to weigh their individual words within them, however...

    use a depth counter to ensure that we find closing brackets

    the problem is that as we modify the string, we will be changing it's length,
    which will mess with iterations...
        we can simply edit the string backwards, that way the operations don't effect
        the length of the parts we're working on... however, if we do this, then we can't
        remove consecutive brackets of the same type, we we would need to remove bracketing
        to the left of the part of the string we're working on.
    
    well, i think we should be fine with a while pos != end of string, and if we find
    a weight to add, break from the enumerate loop and resume at position to re-enumerate
    the new string

    go until we reach a [(, ignore networks < and wildcards {
    if (
        count if consecutive repeating bracket
        look forward to find its corresponding closing bracket
        check if those closing brackets are also consecutive
        add weighting at the end
        remove excessive bracket
        convert bracket to ()
    if [
        count if consecutive repeating bracket
        look forward
            if we find a : or |, return/break from this weight search
            else, to find its corresponding closing bracket
            check if those closing brackets are also consecutive
            add weighting at the end
            remove excessive bracket
            convert bracket to ()

    IF BRACKETS ARE CONSECUTIVE, AND AFTER THEIR SLOPE, BOTH THEIR 
    INNER-NEXT DEPTH ARE THE SAME, IT IS A WEIGHT.
    
    Example using map_depth.
    c, ((a, b))
       ((    ))
    00012222210
    ---^^----vv
   2     ____  2
   1    /===>\ 1
   0___/=====>\0 
    Because 01 can meet on the other side, these are matching
    
    c, (a, (b))
       (   ( ))
    00011112210
    ---^---^-vv
   2        _  2
   1    ___/>\ 1
   0___/=====>\0
    0 and 1 match, but since gradients are not exactly mirrored,
    thier weights should not be combined.

    c, ((a), b)
       (( )   )
    00012211110
    ---^^-v---v
   2     _     2
   1    /=\___ 1
   0___/=====>\0
    Similar idea to above example.
    
    c, ((a), ((b)))
       (( )  (( )))
    000122111233210
    ---^^-v--^^-vvv
   3           _   3
   2     _    />\  2
   1    />\__/==>\ 1
   0___/=========>\0
    Tricky one. Here, 01 open together, so there's a potential that their
    weights should be combined if they close together, but instead 1 closes
    early. We only need to check for closure initial checking depth - 1.
   
    """
    if not BRACKET2WEIGHT:
        return prompt

    re_existing_weight = re.compile(r'(:\d+.?\d*)[)\]]$')
    depths, gradients, brackets = get_mappings(prompt)

    pos = 0
    ret = prompt
    gradient_search = []

    while pos < len(ret):
        current_position = ret[pos:]
        if ret[pos] in '([':
            open_bracketing = re_brackets_open.match(ret, pos)   
            consecutive = len(open_bracketing.group(0))
            gradient_search = ''.join(map(str, reversed(range(int(depths[pos])-1, int(depths[pos])+consecutive))))
            is_square_brackets = True if '[' in open_bracketing.group(0) else False

            insert_at, weight, valid_consecutive = get_weight(
                ret, 
                gradients, 
                depths, 
                brackets, 
                open_bracketing.end(), 
                consecutive, 
                gradient_search,
                is_square_brackets)
            
            if weight:
                # If weight already exists, ignore
                current_weight = re_existing_weight.search(ret[:insert_at + 1])
                if current_weight:
                    ret = ret[:open_bracketing.start()] + '(' + ret[open_bracketing.start()+valid_consecutive:insert_at] + ')' + ret[insert_at + consecutive:]
                else:
                    ret = ret[:open_bracketing.start()] + '(' + ret[open_bracketing.start()+valid_consecutive:insert_at] + f':{weight:.2f}' + ')' + ret[insert_at + consecutive:]
            
            depths, gradients, brackets = get_mappings(ret)
            pos += 1

        match = re_bracket_open.search(ret, pos)

        if not match:   # no more potential weight brackets to parse
            return ret
        
        pos = match.start()

# 在bracket_to_weights函数中,添加对花括号的处理:
        match = re_curly_brackets.search(ret, pos)
        if match:
            weight = 1.05
            ret = ret[:match.start()] + f'(:{weight:.2f})' + ret[match.end():]
            pos = match.start() + 1
            return ret


def depth_to_map(s: str):
    ret = ''
    depth = 0
    for c in s:
        if c in '([':
            depth += 1
        if c in ')]':
            depth -= 1
        ret += str(depth)
    return ret


def depth_to_gradeint(s: str):
    ret = ''
    for c in s:
        if c in '([':
            ret += str('^')
        elif c in ')]':
            ret += str('v')
        else:
            ret += str('-')
    return ret
    

# 为保持一致,在get_mappings函数中添加对花括号的处理:
# def filter_brackets(s: str):
#     return ''.join(list(map(lambda c : c if c in '[]()' else ' ', s)))

def filter_brackets(s: str):
    return ''.join(list(map(lambda c : c if c in '[](){ }' else ' ', s)))


def get_mappings(s: str):
    return depth_to_map(s), depth_to_gradeint(s), filter_brackets(s)


def calculate_weight(d: str, is_square_brackets: bool):
        return 1 / 1.1 ** int(d) if is_square_brackets else 1 * 1.1 ** int(d)


def get_weight(prompt: str, map_gradient: list, map_depth: list, map_brackets: list, pos: int, ctv: int, gradient_search: str, is_square_brackets :bool=False):
    '''
    Returns 0 if bracket was recognized as prompt editing, alternation, or composable
    '''
    # CURRENTLY DOES NOT TAKE INTO ACCOUNT COMPOSABLE?? DO WE EVEN NEED TO?
    # E.G. [a AND B :1.2] == (a AND B:1.1) != (a AND B:1.1) ????
    while pos+ctv <= len(prompt):
        if ctv == 0:
            return prompt, 0, 1
        a, b = pos, pos+ctv
        if prompt[a] in ':|' and is_square_brackets:
            if map_depth[-2] == map_depth[a]:
                return prompt, 0, 1
            if map_depth[a] in gradient_search:
                gradient_search = gradient_search.replace(map_depth[a], '')
                ctv -= 1
        elif (map_gradient[a:b] == 'v' * ctv and
                map_depth[a-1:b] == gradient_search):
            return a, calculate_weight(ctv, is_square_brackets), ctv
        elif ('v' == map_gradient[a] and
                map_depth[a-1:b-1] in gradient_search):
            narrowing = map_gradient[a:b].count('v')
            gradient_search = gradient_search[narrowing:]
            ctv -= 1
        pos += 1
    
    raise Exception(f'Somehow weight index searching has gone outside of prompt length with prompt: {prompt}')


def space_to_underscore(prompt: str):
    # We need to look ahead and ignore any spaces/underscores within network tokens
    # INPUT     <lora:chicken butt>, multiple subjects
    # OUTPUT    <lora:chicken butt>, multiple_subjects
    match = r'(?<!BREAK) +(?!BREAK|[^<]*>)' if SPACE2UNDERSCORE else r'(?<!BREAK)_+(?!BREAK|[^<]*>)'
    replace = '_' if SPACE2UNDERSCORE else ' '

    tokens: str = tokenize(prompt)
    
    return ','.join(map(lambda t: re.sub(match, replace, t), tokens))


def escape_bracket_index(token, symbols, start_index = 0):
    # Given a token and a set of open bracket symbols, find the index in which that character
    # escapes the given bracketing such that depth = 0.
    token_length = len(token)
    open = symbols
    close = ''
    for s in symbols:
        close += brackets_closing[brackets_opening.index(s)]

    i = start_index
    d = 0
    while i < token_length - 1:
        if token[i] in open:
            d += 1
        if token[i] in close:
            d -= 1
            if d == 0:
                return i
        i += 1
    
    return i


def format_prompt(*prompts: list):
    sync_settings()

    ret = []

    for prompt in prompts:
        if not prompt or prompt.strip() == '':
            ret.append('')
            continue

        # Clean up the string
        prompt = normalize_characters(prompt)
        prompt = remove_mismatched_brackets(prompt)

        # Clean up whitespace for cool beans
        prompt = remove_whitespace_excessive(prompt)
        prompt = space_to_underscore(prompt)
        prompt = align_brackets(prompt)
        prompt = space_AND(prompt)      # for proper compositing alignment on colons
        prompt = space_bracekts(prompt)
        prompt = align_colons(prompt)
        prompt = align_commas(prompt)
        prompt = align_alternating(prompt)
        prompt = bracket_to_weights(prompt)

        ret.append(prompt)
    
    return ret


def on_before_component(component: gr.component, **kwargs: dict):
    if 'elem_id' in kwargs:
        if kwargs['elem_id'] in ['txt2img_prompt', 'txt2img_neg_prompt', 'img2img_prompt', 'img2img_neg_prompt']:
            ui_prompts.append(component)
        elif kwargs['elem_id'] == 'paste':
            with gr.Blocks(analytics_enabled=False) as ui_component:
                button = gr.Button(value='🪄', elem_classes='tool', elem_id='format')
                button.click(
                    fn=format_prompt,
                    inputs=ui_prompts,
                    outputs=ui_prompts
                )
                return ui_component


def on_ui_settings():
    section = ('pformat', 'Prompt Formatter')
    shared.opts.add_option(
        'pformat_space_commas',
        shared.OptionInfo(
            True,
            'Add a spaces after comma',
            gr.Checkbox,
            {'interactive': True},
            section=section
        )   
    )
    shared.opts.add_option(
        'pfromat_bracket2weight',
        shared.OptionInfo(
            True,
            'Convert excessive brackets to weights',
            gr.Checkbox,
            {'interactive': True},
            section=section
        )   
    )
    shared.opts.add_option(
        'pfromat_space2underscore',
        shared.OptionInfo(
            False,
            'Convert spaces to underscores (default: underscore to spaces)',
            gr.Checkbox,
            {'interactive': True},
            section=section
        )
    )

    sync_settings()


def sync_settings():
    global SPACE_COMMAS, BRACKET2WEIGHT, SPACE2UNDERSCORE
    SPACE_COMMAS = shared.opts.pformat_space_commas
    BRACKET2WEIGHT = shared.opts.pfromat_bracket2weight
    SPACE2UNDERSCORE = shared.opts.pfromat_space2underscore


script_callbacks.on_before_component(on_before_component)
script_callbacks.on_ui_settings(on_ui_settings)