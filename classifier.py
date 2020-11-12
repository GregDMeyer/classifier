
from argparse import ArgumentParser
from os.path import isfile, join, split, basename
import csv
import readline
from glob import iglob
from time import sleep
import sys
from subprocess import Popen, PIPE, STDOUT

SPEC_FILE = join(split(__file__)[0], 'default_species.txt')

def parse_args():
    p = ArgumentParser(description="Input classification data to a CSV file. If the "
                                   "output file already exists, it will be opened and "
                                   "appended to. Press tab to autocomplete known species names.")

    p.add_argument("img_directory", help="the directory containing the images")
    p.add_argument("initials", help="your initials (to mark the output CSV)")
    p.add_argument("species_names", nargs='?', default=SPEC_FILE,
                   help="A list of additional species names for autocomplete "
                        "[default: '"+SPEC_FILE+"']")

    args = p.parse_args()

    # check that the species file exists
    if not isfile(args.species_names):
        if args.species_names == SPEC_FILE:
            args.species_names = None
        else:
            err_str = "default species names file '{}' not found".format(args.species_names)
            raise RuntimeError(err_str)

    return args

class Classifier:
    def __init__(self, img_dir, initials):

        self.img_dir = img_dir
        self.img_files = None
        self.get_img_files(self.img_dir)

        if not self.img_files:
            raise FileNotFoundError("no .jpg images found in directory {}".format(img_dir))

        self.sample = self.img_files[0].split('_')[0]
        self.f = join(self.img_dir, self.sample+"_species_"+initials+".csv")

        self.data = {}              # will be dict of obj -> (species, confidence)
        self.known_species = set()
        self.lower_species = set()  # the species, in lowercase

        self.csv_headers = ['Sample Name', 'Obj. #', 'Species', 'Confidence']

        if isfile(self.f):
            print("Loading data from '{}'...".format(self.f))
            self._load_existing()
            print("Sample name: {}".format(self.sample))
            print("{} objects already in file.".format(len(self.data)))
        else:
            print("Generating new CSV file '{}'".format(self.f))

        self.img_idx = 0

    def run(self):
        # start up the GUI
        self.display_proc = Popen([sys.executable, 'display.py'], stdin=PIPE)
        self.data_loop()
        self.display_proc.stdin.close()

    def data_loop(self):
        try:
            while self.enter_data():
                pass
        except KeyboardInterrupt:
            pass

        if self.img_idx >= len(self.img_files):
            print('All images identified!')

    def get_img_files(self, img_dir):
        self.img_files = sorted(basename(x) for x in iglob(join(img_dir, "*.jpg")))

    def gen_filename(self, obj_num):
        return '_'.join([self.sample, 'obj'+str(obj_num).zfill(5), 'plane000.jpg'])

    def split_filename(self, fname):
        sample, obj, _ = fname.split('_')
        obj = int(obj[3:])
        return sample, obj

    def _load_existing(self):
        with open(self.f, newline='') as csvfile:
            r = csv.reader(csvfile)

            try:
                header = next(r)
            except StopIteration:
                raise RuntimeError('file "{}" seems to be empty? delete it to '
                                   'have classifier make a new file'.format(self.f))

            if header != self.csv_headers:
                print(header)
                print(self.csv_headers)
                raise RuntimeError('first line of file does not match correct column labels')

            for name, obj, spec, conf in r:
                try:
                    obj = int(obj)
                except ValueError:
                    err_str = "invalid object number '{}' in row {}".format(obj, len(self.data))
                    raise RuntimeError(err_str) from None

                if name != self.sample:
                    raise RuntimeError("File contains different sample names? '{}' and '{}' "
                                       "found".format(self.sample, name))

                fname = self.gen_filename(obj)
                obj_file = join(self.img_dir, fname)
                if not isfile(obj_file):
                    raise RuntimeError("No file '{}' found for object in CSV".format(obj_file))

                self._register_species(spec)

                if fname in self.data:
                    raise ValueError("file '{}' found twice in data?".format(fname))

                self.data[fname] = (spec, conf)

    def _register_species(self, spec):
        if spec.lower() not in self.lower_species:
            self.lower_species.add(spec.lower())
            self.known_species.add(spec)

    def add_names_from_file(self, filename):
        with open(filename) as f:
            for line in f:
                self._register_species(line.strip())

    def enter_data(self):
        # data has already been entered for this one
        while self.img_idx < len(self.img_files) and self.img_files[self.img_idx] in self.data:
            self.img_idx += 1

        if self.img_idx >= len(self.img_files):
            return False

        fname = self.img_files[self.img_idx]
        sample, obj = self.split_filename(fname)

        self.display_proc.stdin.write((join(self.img_dir, fname)+'\n').encode())
        self.display_proc.stdin.flush()

        if sample != self.sample:
            raise RuntimeError("Image has different sample name? '{}' and '{}' "
                               "found".format(self.sample, name))

        print()
        print("Object number: {}".format(obj))

        spec = Completer(self.known_species).get_input("Enter species name: ")
        spec = spec.strip()

        if spec == 'quit':
            return False

        self._register_species(spec)

        conf = input("Confidence (1=low, 2=med, 3=high): ")
        while conf not in ["1", "2", "3"]:
            conf = input("Type 1, 2, or 3 for confidence: ")
        conf = int(conf)

        if fname in self.data:
            raise ValueError("file '{}' already in data?".format(fname))

        self.data[fname] = (spec, conf)
        self._write_file()

        return True

    def _write_file(self):
        with open(self.f, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(self.csv_headers)
            for fname, val in sorted(self.data.items(), key=lambda x: x[0]):
                sample, obj = self.split_filename(fname)
                writer.writerow([sample, str(obj).zfill(5)] + list(val))

class Completer:
    def __init__(self, options):
        self.options = options
        self.matches = None

    def complete(self, text, state):
        if state == 0:
            if text:
                self.matches = [s for s in self.options
                                if s.lower().startswith(text.lower())]
            else:
                self.matches = self.options

        if state < len(self.matches):
            rtn = self.matches[state]
        else:
            rtn = None

        return rtn

    def get_input(self, query_str=''):
        readline.set_completer(self.complete)
        readline.set_completer_delims('')
        readline.parse_and_bind('tab: complete')
        rtn = input(query_str)
        readline.set_completer(None)
        return rtn

def main():
    args = parse_args()

    print('Welcome to the species classifier!')
    print('Press tab to autocomplete species names; type "quit" to quit.')
    print('The file is saved every time a new object is entered.')
    print()

    c = None
    c = Classifier(args.img_directory, args.initials)
    if args.species_names is not None:
        c.add_names_from_file(args.species_names)

    c.run()

    print()
    print()
    if c is None or not c.data:
        print('No objects recorded, file not written. Goodbye!')
    else:
        print('{} objects stored in file. Goodbye!'.format(len(c.data)))

if __name__ == '__main__':
    main()
