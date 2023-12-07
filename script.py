import json, uuid, time, re, os, threading
from datetime import datetime
from pathlib import Path

#ooga specific imports
import gradio as gr
from modules import (
    chat,
    shared,
    training,
    ui,
    ui_chat,
    ui_default,
    ui_file_saving,
    ui_model_menu,
    ui_notebook,
    ui_parameters,
    ui_session,
    utils,
    presets
)

from modules.ui import create_refresh_button, apply_interface_values, list_model_elements, list_interface_input_elements
from modules.utils import gradio
from modules.logging_colors import logger
from modules.models_settings import update_model_parameters
from modules.ui_model_menu import load_model_wrapper, update_truncation_length

class RepeatedTimer(object):
    def __init__(self, interval, function, *args, **kwargs):
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.is_running = False
        self._timer = None
        self.next_call = time.time()

    def _run(self):
        self.is_running = False
        self.function(*self.args, **self.kwargs)
        self.start()

    def start(self):
        if not self.is_running:
            self.next_call = time.time() + self.interval
            self._timer = threading.Timer(self.next_call - time.time(), self._run)
            self._timer.start()
            self.is_running = True

    def stop(self):
        if self.is_running:
            self._timer.cancel()
            self.is_running = False

#variables that get saved
params = { 
    "name": "session_manager", #change this & folder when done
    "display_name": "Session Manager",
    "custom string": "n/a",
    "stop_save": True,
    "auto_save": True,
    "auto_save_t": 30,
    "auto_load": True,
    "auto_load_n": True,
    "auto_load_m": True,
    "auto_session": False,
    "verbose": False,
    "default_session": None,
    "default_checkpoint": None,
    "output_path": None
}

#temps
glob = { 
    'output_textbox': None, 
    'input_textbox': None, 
    'old_output': None,
    'prompt': None,
    'reply': None,
    'session_name': None,
    'session_data': {},
    'session_mtime': -1,
    'default_last': None,
    'notebook_last': None,
    'last_save': None,
    'default_session': None,
    'default_checkpoint': None,
    'auto_loaded': False,
    "output_path": None,
    "unpreset_hold": False
}

gui = {
    'stop_save': None,
    'auto_save': None,
    'auto_load': None,
    'auto_load_n': None,
    'auto_load_m': None,
    'auto_session': None,
    'verbosity': None,
    'new_button': None,
    'save_button': None,
    'load_button': None,
    'clear_button': None,
    'session_select': None,
    'session_refresh': None,
    'session_delete': None,
    'checkpoint_select': None,
    'checkpoint_refresh': None,
    'checkpoint_delete': None,
    'info_panel': None,
    'json_reader': None
}

#from ui.py list_interface_input_elements()
#everything not lost will be saved

# Chat elements
input_elements_filter = [
    'textbox',
    'start_with',
    'character_menu',
    'history',
    'name1',
    'name2',
    'greeting',
    'context',
    'mode',
    'instruction_template',
    'name1_instruct',
    'name2_instruct',
    'context_instruct',
    'turn_template',
    'chat_style',
    'chat-instruct_command',
]

# Notebook/default elements
input_elements_filter += [
    #'textbox-notebook',
    #'textbox-default',
    #'output_textbox',
    'prompt_menu-default',
    'prompt_menu-notebook',
]

#static strings
folder_path=Path(f'{os.getcwd()}/extensions/{params["name"]}/')
stamp_format = "%Y-%m-%d@%H-%M-%S"
illegal_chars = r'[\/:*?"<>|\n ]'

def extract_datetime(filename):
    try:
        return datetime.strptime(filename.split('_')[0], stamp_format)
    except: #ValueError:
        return datetime.min
    
    return

def get_available_sessions():
    return sorted(set((k.stem for k in glob["output_path"].glob('*.json'))), key=extract_datetime, reverse=False)

def get_newest_session():
    sessions = get_available_sessions()
    if not sessions:
        return None

    sorted_timestamps = sorted(sessions, key=extract_datetime)
    newest_timestamp = max(sorted_timestamps, key=extract_datetime)
    return newest_timestamp

def update_last_saved_ui():
    stamped = stamp()
    glob['last_save'] = stamped
    return stamped

def stamp():
    return datetime.now().strftime(stamp_format)

def session_path(session_name):
    return glob["output_path"].joinpath(f'{session_name}.json')
   
def load_settings():
    global params
    data = {}
    file_path = folder_path.joinpath('settings.json')
    
    if file_path.exists():
        try:
            with open(file_path, 'r') as file:
                data = json.load(file)
        except:
            print(f"{params['name']}: failed to load settings")
    
    if params['verbose']:
        print(f"{params['name']}: loading settings {data}")

    params.update(data)
    return data

def save_settings():
    file_path = folder_path.joinpath('settings.json')

    if params['verbose']:
        print(f"{params['name']}: saving settings {params}")

    try:
        with open(file_path, 'w') as file:
            json.dump(params, file, indent=2)
    except:
        print(f"{params['name']}: failed to save settings")

    return

def clear_ui():
    global glob
    #glob['output_textbox'] = None, 
    #glob['input_textbox'] = None, 
    glob['old_output'] = None,
    glob['prompt'] = None,
    glob['reply'] = None,
    return None, None

def delete_session(session_name):
    file_path = session_path(session_name)

    if not file_path.exists():
        return

    try:
        os.remove(file_path)
        if params['verbose']:
            print(f"{params['name']}: {file_path} deleted")

    except Exception as e:
        print(f"{params['name']}: {e}")

    return file_path
    
def rename_session(new_session_name):
    global glob
    file_path = session_path(glob['session_name'])
    new_path = session_path(new_session_name)

    if not file_path.exists():
        return None

    try:
        os.rename(file_path, new_path)
    except Exception as e:
        print(f"{params['name']}: {e}")

    if params['verbose']:
        print(f"{params['name']}: {glob['session_name']} renamed to {new_session_name}")

    glob['session_name'] = new_session_name
    return new_session_name

#todo: make these more robust by returning None when structure is malformed
def read_session(session_name):
    global gui
    global glob

    data = {}
    file_path = session_path(session_name)
    
    if not file_path.exists():
        return None

    session_mtime = os.path.getmtime(file_path)
    if(session_mtime != glob['session_mtime']): #session modified
        glob['session_mtime'] = session_mtime
        try:
            with open(file_path, 'r') as file:
                data.update(json.load(file))
                glob['session_data'] = data

        except Exception as e:
            print(f"An error occurred loading the json info: {e}")

    else: #file has not been changed, use cache
        data = glob['session_data']

    return data

def read_checkpoints(session_name):
    session_data = read_session(session_name)
    if not session_data:
        return []

    return sorted(list(session_data.keys()))

def get_newest_checkpoint(session_name):
    checkpoints = read_checkpoints(session_name)
    if not checkpoints:
        return None

    sorted_timestamps = sorted(checkpoints, key=extract_datetime)
    return max(sorted_timestamps, key=extract_datetime)

def read_checkpoint_data(session_name, checkpoint_name):
    session_data = read_session(session_name)
    if not session_data or checkpoint_name not in session_data:
        return {}

    return session_data[checkpoint_name]

def load_checkpoint(session_name, checkpoint_name, state):
    global glob

    if session_name == None or checkpoint_name == None:
        return None

    if params['verbose']:
        print(f"{params['name']}: loading session {session_name}")
        print(f"{params['name']}: loading checkpoint {checkpoint_name}") 

    glob['session_name'] = session_name
    generate_params = {}
    checkpoint_data = {}

    if checkpoint_name == "auto_save":
        auto_data = read_checkpoint_data(session_name, checkpoint_name)
        newest_checkpoint = get_newest_checkpoint(session_name)
        checkpoint_data = read_checkpoint_data(session_name, newest_checkpoint)
        checkpoint_data.update(auto_data)
        gr.Info("Restoring Autosave...")
    else:
        checkpoint_data = read_checkpoint_data(session_name, checkpoint_name)
        gr.Info("Restoring Session...")

    if not checkpoint_data:
        return

    output_input = ""
    output_output = ""

    #prompt and reply strings supercede parameter stringsa
    if 'parameters' in checkpoint_data:
        generate_params.update(checkpoint_data['parameters'])

    if 'prompt' in checkpoint_data and checkpoint_data['prompt'] != None:
        output_input += checkpoint_data['prompt']
        if 'textbox-default' in generate_params: 
            generate_params['textbox-default'] = checkpoint_data['prompt']
        if 'textbox-notebook' in generate_params:
            generate_params['textbox-notebook'] = checkpoint_data['prompt']
        #if 'output_textbox' in generate_params:
            #todo: causes prompt to double every time
            #output_textbox += checkpoint_data['prompt']

        glob['default_last'] = checkpoint_data['prompt']
        glob['notebook_last'] = checkpoint_data['prompt']
        glob['prompt'] = checkpoint_data['prompt']
        glob['input_textbox'] = checkpoint_data['prompt']
        
    if 'reply' in checkpoint_data and checkpoint_data['reply'] != None:
        output_output += checkpoint_data['reply']
        #glob['reply'] = checkpoint_data['reply']

    
    if output_output or output_input:
        if not output_output and 'output_textbox' in checkpoint_data:
            output_output = checkpoint_data['output_textbox']

        if not output_input and 'textbox-default' in checkpoint_data:
            output_input = generate_params['textbox-default']

        generate_params['output_textbox'] = output_input + output_output

    state.update(generate_params)

    #load model
    #update_model_parameters(state)
    #load_model_wrapper(checkpoint_data['model'], shared.gradio['loader'], autoload=True) #=gradio('model_status')

    return state, *[generate_params[k] for k in generate_params]

#todo someday: make append functions append instead of dump
def dump_session(session_name, session_data):
    file_path = session_path(session_name)

    with open(file_path, 'w') as file:
        json.dump(session_data, file, indent=2)

    glob['session_data'] = session_data
    glob['session_data_mtime'] = os.path.getmtime(file_path)
    update_last_saved_ui()
    return session_name

def delete_checkpoint(session_name, checkpoint_name):
    session_data = read_session(session_name)
    if not session_data:
        return
    del session_data[checkpoint_name]
    return dump_session(session_name, session_data)

#pressing save very fast overwrites checkpoints in the same second, probably fine idk
def append_checkpoint(session_name, checkpoint_data):
    stampd = stamp()
    new_data = {} 

    #load file if exists
    session_data = read_session(session_name)
    if session_data:
        new_data.update(session_data)
    
    new_data[stampd] = checkpoint_data

    if params['verbose']:
        print(f"{params['name']}: writing checkpoint {stampd}...")

    dump_session(session_name, new_data)
    return new_data

def append_auto_save(session_name, data):
    session_data = read_session(session_name)
    stampd = stamp()

    if not session_data:
        return None

    session_data['auto_save'] = data

    if params['verbose']:
        print(f"{params['name']}: autosaving {stampd}...")

    dump_session(session_name, session_data)
    return session_name

def auto_save(input_text):
    global glob
    
    new=glob["output_textbox"] if glob["output_textbox"] else ""
    old=glob["old_output"] if glob["old_output"] else ""
    diff=new[len(old):] 

    checkpoint_data = {
        'timestamp': stamp(),
        'prompt': glob["input_textbox"],
        'reply': new[len(glob["input_textbox"]):] if glob["input_textbox"] else ""
    }

    if diff != "": #prevents the timer startup bug
        glob["old_output"] = glob["output_textbox"] 
        append_auto_save(glob["session_name"], checkpoint_data)
        gr.Info("Session Auto Saved")
        
    return checkpoint_data

rt = RepeatedTimer(params["auto_save_t"], auto_save, "")

def save_session(string=""):
    global glob

    #get current input elements & filter out unwanted info
    input_elements = shared.input_elements #all elements
    elements = {}
    for i, elmt in enumerate(input_elements): 
        if elmt not in input_elements_filter: #filter
            elements[elmt] = input_elements[i]

    #get current input values, filter from prev
    interface_state = shared.persistent_interface_state
    parameters = {}
    for elmt in interface_state:
        if elmt in elements: #filter
            parameters[elmt] = interface_state[elmt]

    #write captured textboxes to params
    parameters['output_textbox'] = glob['output_textbox']
    parameters['textbox-default'] = glob['input_textbox']

    #adapter = None #getattr(shared.model,'active_adapter','None') leftover from AutoSave, returns a non serializable method for gptq models?
    checkpoint_data = {"model": shared.model_name, "prompt" : glob['prompt'], "reply":string,  "parameters": parameters}
    append_checkpoint(glob["session_name"], checkpoint_data)

    gr.Info("Session Saved")
    return session_path

def save_session_ui():
    return save_session(glob['output_textbox'])

#todo: add a naming convention configuration string
def new_session(string=""):
    global glob
    glob["input_textbox"] = None
    glob["output_textbox"] = None
    glob['old_output'] = None
    glob['prompt'] = None
    glob['reply'] = None

    if not string:
        string = ""

    #todo: maybe add a slider or param for length
    fill = "_" + str(uuid.uuid4())
    shorter_string = string[:len(fill)]
    filler = fill[:(len(fill)-len(shorter_string))]
    
    dirty_name = f"{stamp()}_{shorter_string}"
    counter = 1
    while os.path.exists(session_path(dirty_name)):
        dirty_name = f"{stamp()}_{shorter_string}({counter})"
        counter += 1

    clean_name = re.sub(illegal_chars, '_', dirty_name) #.replace('\n', '_')
    new_name = clean_name + filler
    glob['session_name'] = new_name

    if params['verbose']:
        print(f"{params['name']}: new session {new_name} created")

    save_session_ui()
    return new_name

def new_session_ui():
    return new_session(glob['input_textbox'])

def input_modifier(string, state):
    global glob
    global params

    if params['auto_session']:
        changed = False

        #probably just {string} would be sufficient here
        default=state['textbox-default']
        notebook=state['textbox-notebook']

        #if the new prompt is the old prompt+the old output, then its a continue, dont make a new session
        if (glob['prompt'] and glob['reply']) and (glob['prompt']+glob['reply'] != string):         
            #if either prompt changed
            if default != glob['default_last']:
                glob['default_last'] = default
                changed = True

            if notebook != glob['notebook_last']:
                glob['notebook_last'] = notebook
                changed = True

        if changed:
            if params['verbose']:
                print(f"{params['name']}: prompt changed")

            new_session(string)

    glob["input_textbox"] = string
    glob['prompt'] = string

    if params['auto_save']:
        print(f"{params['name']}: autosaving every {params['auto_save_t']} seconds")
        rt.interval = params['auto_save_t']
        rt.start()
    
    save_session_ui()
    return string

def output_modifier(string):
    global glob

    if params['auto_save']:
        rt.stop()
        if params['verbose']:
            print(f"{params['name']}: autosaving suspended")

    if params['stop_save']:
        save_session(string)

    glob['reply'] = string
    glob["output_textbox"] = string
    return string

#fu - frontend update
def fu_checkpoints_ui(session_name):
    global gui

    if not session_path(session_name).exists():
        return None

    checkpoints = read_checkpoints(session_name)
    latest_checkpoint = get_newest_checkpoint(session_name)
    args = {'choices': checkpoints, 'value': latest_checkpoint}
    for k, v in args.items():
        setattr(gui['checkpoint_select'], k, v)

    return gr.update(**(args or {}))

def fu_sessions_ui():
    global gui

    session_name = glob['session_name']

    if not session_path(session_name).exists():
        session_name = get_newest_session()

    sessions = get_available_sessions()

    args = {'choices': sessions, 'value': session_name}
    for k, v in args.items():
        setattr(gui['session_select'], k, v)

    return gr.update(**(args or {}))

#workaround for the presets menu kicking in when the interface is reloaded
def fu_unsets_your_pre(prompt_preset_dropdown):
    global glob

    if not params['auto_load']:
        return None

    if glob['unpreset_hold']:
        glob['unpreset_hold'] = False
        return None
    
    #if prompt_preset_dropdown != None and shared.persistent_interface_state['prompt_menu-default'] != None:
    #    return None

    time.sleep(1) #no getting around this
    
    args = {'value': glob['prompt']}
    for k, v in args.items():
        setattr(shared.gradio['textbox-default'], k, v)

    return gr.update(**(args or {}))

def fu_dont_unset():
    global glob
    glob['unpreset_hold'] = True

#bu - backend update
def bu_session_params(session_name):
    global params
    params['default_session'] = session_name
    return 1

def bu_checkpoint_params(checkpoint_name):
    global params
    params['default_checkpoint'] = checkpoint_name
    return 1

#todo: update dropdowns when the new button is pressed. checkpoints also
def ui():
    global glob
    global gui

    #glob['unpreset_hold'] = False

    #setup defaults 
    info = "" #f"Last Saved: {glob['last_save']} \\n Current Session: {glob['session_name']}"
    sessions=get_available_sessions()

    default_session = params['default_session']
    if default_session == None or default_session not in sessions or (params['auto_load'] and params['auto_load_n']):
        default_session = get_newest_session()

    checkpoints = read_checkpoints(default_session)

    default_checkpoint = params['default_checkpoint']
    if default_checkpoint == None or default_checkpoint not in read_checkpoints(default_session) or (params['auto_load'] and params['auto_load_n']):
        default_checkpoint = get_newest_checkpoint(default_session)
        autosave_data = read_checkpoint_data(default_session, 'auto_save')
        if autosave_data and autosave_data['timestamp'] > default_checkpoint:
            default_checkpoint = 'auto_save'        

    #todo: select save folder button?
    #define ui elements
    with gr.Row():
        with gr.Column():
            with gr.Row():
                with gr.Group():
                    with gr.Row():
                        gui['stop_save'] = gr.Checkbox(value=params['stop_save'], label='Save on Stop')
                        #todo: make info box update
                        gui['info_panel'] = gr.Markdown(info)
                        
                    with gr.Row():
                        gui['auto_save'] = gr.Checkbox(value=params['auto_save'], label='Auto Save', info='Every X Seconds')
                        gui['auto_save_t'] = gr.Slider(30, 900, step=30, value=params['auto_save_t'], show_label=False)
                    
                    with gr.Row():
                        with gr.Column():
                            gui['auto_load'] = gr.Checkbox(value=params['auto_load'], label='Auto Load')
                        with gr.Column():
                            with gr.Row():
                                gui['auto_load_n'] = gr.Checkbox(value=params['auto_load_n'], label='Most Recent')
                                gui['auto_load_m'] = gr.Checkbox(value=False, label='Load Model', interactive=False)
                    
                    gui['auto_session'] = gr.Checkbox(value=params['auto_session'], label='Auto Session', info='New Session When Prompt Changes')
                    gui['verbosity'] = gr.Checkbox(value=params['verbose'], label='Verbose')

        with gr.Column():
            with gr.Group():
                gui['save_button'] = gr.Button(value="Checkpoint")

                with gr.Row():
                    gui['new_button'] = gr.Button(value="New")
                    gui['clear_button'] = gr.Button(value="Clear")
                    
            with gr.Group():
                with gr.Row():
                    gui['load_button'] = gr.Button(value="Load")
                    gui['rename_button'] = gr.Button(value="Rename")
                with gr.Row():
                    gui['session_select'] = gr.Dropdown(choices=sessions, value=default_session, label='Session file: ', elem_classes='slim-dropdown', interactive=True, allow_custom_value=True, container=True)
                    gui['session_refresh'] = create_refresh_button(gui['session_select'], lambda: None, lambda: {'choices': get_available_sessions()}, 'refresh-button', interactive=True)
                    gui['session_delete'] = gr.Button('🗑️', elem_classes='refresh-button')

                with gr.Row():
                    gui['checkpoint_select'] = gr.Dropdown(choices=checkpoints, value=default_checkpoint, label='Checkpoint:', elem_classes='slim-dropdown', interactive=True, container=True)
                    gui['checkpoint_refresh'] = create_refresh_button(gui['checkpoint_select'], lambda: None, lambda: {'choices': read_checkpoints(gui['session_select'].value)}, 'refresh-button', interactive=True)
                    gui['checkpoint_delete'] = gr.Button('🗑️', elem_classes='refresh-button')

    with gr.Row():
        with gr.Row():
            with gr.Accordion("JSON Preview", open=False):
                gui['json_reader'] = gr.JSON()
            
            gui['json_reader_refresh'] = create_refresh_button(gui['json_reader'], lambda: None, lambda: {'value': read_checkpoint_data(gui['session_select'].value, gui['checkpoint_select'].value)}, 'refresh-button', interactive=True)

    #toggles events
    gui['stop_save'].change(lambda x: params.update({"stop_save": x}), gui['stop_save'], None).then(save_settings)
    gui['auto_save'].change(lambda x: params.update({"auto_save": x}), gui['auto_save'], None).then(save_settings)
    gui['auto_load'].change(lambda x: params.update({"auto_load": x}), gui['auto_load'], None).then(save_settings)
    gui['auto_load_n'].change(lambda x: params.update({"auto_load_n": x}), gui['auto_load_n'], None).then(
        bu_session_params, gui['session_select']).then(
        bu_checkpoint_params, gui['checkpoint_select']).then(save_settings)
    gui['auto_load_m'].change(lambda x: params.update({"auto_load_m": x}), gui['auto_load_m'], None).then(save_settings)
    gui['auto_session'].change(lambda x: params.update({"auto_session": x}), gui['auto_session'], None).then(save_settings)
    gui['verbosity'].change(lambda x: params.update({"verbose": x}), gui['verbosity'], None).then(save_settings)

    #slider events params
    gui['auto_save_t'].release(lambda x: params.update({"auto_save_t": x}), gui['auto_save_t'], None) 

    #buttons events 
    gui['load_button'].click(load_checkpoint, [gui['session_select'], gui['checkpoint_select']] + gradio('interface_state'), 
        gradio('interface_state') + gradio(presets.presets_params())).then(
        apply_interface_values, gradio('interface_state'), gradio(list_interface_input_elements()))

    gui['rename_button'].click(rename_session, gui['session_select']).then(fu_sessions_ui, outputs=gui['session_select']).then(save_settings)
    gui['checkpoint_delete'].click(delete_checkpoint, [gui['session_select'], gui['checkpoint_select']]).then(fu_checkpoints_ui, inputs=gui['session_select'], outputs=gui['checkpoint_select']).then(save_settings)
    gui['session_delete'].click(delete_session, gui['session_select']).then(fu_sessions_ui, outputs=gui['session_select']).then(save_settings)
    gui['save_button'].click(save_session_ui).then(fu_checkpoints_ui, inputs=gui['session_select'], outputs=gui['checkpoint_select']).then(save_settings)
    gui['new_button'].click(new_session_ui).then(fu_sessions_ui, outputs=gui['session_select']).then(save_settings)
    gui['clear_button'].click(clear_ui, outputs=[shared.gradio['textbox-default'], shared.gradio['output_textbox']])

    #update ui elements events (making these was just...awful)
    gui['session_select'].change(fu_checkpoints_ui, inputs=gui['session_select'], outputs=gui['checkpoint_select']).then(
        bu_session_params, gui['session_select']).then(save_settings)
    gui['checkpoint_select'].change(read_checkpoint_data, [gui['session_select'], gui['checkpoint_select']], gui['json_reader']).then(
        bu_checkpoint_params, gui['checkpoint_select']).then(save_settings)

    #external textbox monitoring
    shared.gradio['output_textbox'].change(lambda x: glob.update({'output_textbox': x}), shared.gradio['output_textbox'], [])
    shared.gradio['textbox-default'].change(lambda x: glob.update({'input_textbox': x}), shared.gradio['textbox-default'], [])

    #hook to undo preset
    shared.gradio['prompt_menu-default'].change(fu_unsets_your_pre, inputs=shared.gradio['prompt_menu-default'], outputs=shared.gradio['textbox-default'])
    shared.gradio['prompt_menu-default'].input(fu_dont_unset) #be slightly less aggressive 

    #load at last possible moment
    if params['auto_load']:
        if not glob['auto_loaded']:
            glob['auto_loaded'] = True
            load_checkpoint(default_session, default_checkpoint, shared.persistent_interface_state)
    else:
        new_session_ui()

def setup():
    global glob
    load_settings()
    
    #load customizable output path from params
    if params["output_path"] == None:
        glob["output_path"] = Path(f'{os.getcwd()}/extensions/{params["name"]}/output')

    else:
        glob["output_path"] = Path(params["output_path"])

    if not glob["output_path"].exists():
        glob["output_path"].mkdir()

    if params['verbose']:
        print(f"{params['name']}: output path {params['output_path']}")

#todo: maybe break up this huge file into multiples, ui, filesaving, etc
#save on emergency exit?
#todo: make everything support chat, default, notebook