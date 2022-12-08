## Classifier

This repository contains a script to help quickly flip through a directory of specimen images, and manually record the species of each. The species can be tab-completed based on a list of known species names. Optionally can also query for information about reproductive mode. If a set of images has already been partially classified, the script will start back up where you left off.

Run `python classifier.py --help` for information about how to run it.

For an example of how the script works, try running:

``` bash
python classifier.py test_files/ GDKM --repro
```

### Requirements

The script is written for Python 3. It also requires Tkinter, which you may need to install on your system.

Install the other required Python packages with `pip install -r requirements.txt`.
