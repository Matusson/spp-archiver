# SPP Archiver
## About
Substance Painter stores baked mesh maps within the .spp file itself. This is convenient, but these files can get pretty big.
As the mesh maps can be re-baked at any time, storing them within the file itself is unnecessary, and at high resolution they're the biggest contributor to .spp file sizes. There are no Substance tools that would help to remove those maps.

This plugin allows you to find all spp files in a directory (and its subdirectories) and automatically re-bake all mesh maps at 2x2 resolution (the API doesn't allow deleting maps). Optionally, it can also delete all autosave files. These functions can particularly help you in archiving old files.

## Installation
1. Open Substance Painter
2. Top toolbar > Python > Plugins Folder
2. Put the "SPP Archiver.py" script in the "plugins" directory
3. Back in Painter, top toolbar > Python > Reload Plugins Folder
4. Python > SPP Archiver

This should open the SPP Archiver window. You can now also access it through Window > Views > SPP Archiver.

## Usage
The use is self-explanatory. Press "Select directory..." to select a folder in which you want to archive the .spp files. The plugin will search through the folder and all subfolders, and show you a list of found files. Please review the list and make sure you want to archive them. You may also press the checkbox to automatically delete autosave files. 
Once all files are archived, Painter might crash. This is normal and won't affect the outcome.

The plugin was designed for v7.4.1 but should work in other versions.

## Contributing
All contributions are welcome! 

## License
Distributed under the MIT License.
