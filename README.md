# Session Manager

This was created to fill the void left by the removal of ooba's save/load session, expanded/forked/derived from the Autosave extension with features and options I personally find useful.

(its clunky in parts mostly because I'm unfamiliar with gradio)

Feel free to use/extend/modify. PR fixes welcome.

![picture of a user interface with toggles, sliders, and buttons](https://github.com/bekkayya/session_manager/blob/main/menus_preview.png)

### sessions
 save data is broken into session files, which contain checkpoints and a rolling autosave  

> checkpoints contain the prompt, response, parameters, and model settings 

> autosaves contain the current state of the input and output text boxes

session files can then have their checkpoint data and parameters loaded manually or automatically

### features:
- optional:
  - save on stop - starting and stopping generation creates a checkpoint (forked feature from AutoSave)
  - auto save - updates the rolling autosave with new data every x seconds
  - auto load - auto loads the last selected, or newest, session when the server finishes booting
  - auto session: creates a new session whenever a change to the prompt is made
- file management - create, select, rename, and delete, sessions and checkpoints from the ui
- json preview - expandable preview to see the selected checkpoint's raw json
- custom save location config - output_path in settings.json can be used to overwrite the default save location
- futureproofish - settings are collected from the internal ooba functions, so new settings and sliders should be automatically saved. 

### feature todo:
- save string customization
- chat & notebook functionality
- capture cli output, parameters preset

### known issues:
- model parameters are saved but cant be loaded due to I cant figure it out, feature is currently disabled
- sometimes gradio dropdowns have a different entry ticked than selected 
  - manual solution: select something else and return to force an update
- currently only designed for the default page, notebook might work somewhat, chat probably not at all
- autosaving and manual checkpointing bump into undefined gradio behavior and can lag behind by several tokens
- checkpointing at the very start before any generation often captures nothing, not much to be done about that


