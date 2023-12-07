what this is:
    created to fill the void left by the removal of the save/load session menu from ooga
    expanded/forked/derived from the Autosave extension
    with features and options I personally find useful

    save data is broken into sessions, which contain checkpoints and a rolling autosave
        each checkpoint contains the prompt, response, and parameters, and model settings
        autosaves contain the current state of the input and output textboxes

    saved session checkpoints and its parameters can then be loaded manually or automatically

    The code is clunky in parts mostly because I'm unfamiliar with gradio. 
    Feel free to use/extend/modify. PR fixes welcome.

features:
    save on stop - starting and stopping generation creates a checkpoint
    auto save - updates the rolling autosave with new data every x seconds
    auto load session - auto loads the last selected, or newest, session when the server finishes booting
    file management - create, select, rename, and delete sessions from the ui
    json preview - expandable preview to see the selected checkpoint's raw json
    custom save location config - output_path in settings.json can be used to overwrite the default save location
    futureproofish - settings are collected from the internal ooba functions, so new settings and sliders should be automatically saved. 

feature todo:
    save string customization
    chat & notebook functionality
    capture cli output, selected params preset

known issues:
    model paramters are saved but cant be loaded due to I cant figure it out, feature is currently disabled
    sometimes gradio dropdowns have a different entry ticked than selected
        manual solution: select something else and return to make the json reader update
    currently only designed for the default page, notebook might work somewhat, chat probably not at all
    autosaving and manual checkpointing bump into undefined gradio behavior and can lag behind by several tokens
    checkpointing at the very start before any generation often captures nothing, not much to be done about that
    
    
    #autoloading fights with the presets menu since they both try to do the same thing when ooba calls ui setup
    #    manual solution: waiting to change tabs until everything is completely loaded seems to help and/or manually press load

