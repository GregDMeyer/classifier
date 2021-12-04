#!/usr/bin/env python3

from argparse import ArgumentParser
from os.path import isfile, join, split, basename
import csv
from glob import iglob
from time import sleep
import sys
from subprocess import Popen, PIPE, STDOUT

try:
    import gnureadline as readline
except ImportError:
    import readline

SPEC_FILE = join(split(__file__)[0], 'default_species.txt')
DISPLAY_FILE = join(split(__file__)[0], 'display.py')

def parse_args():
    p = ArgumentParser(description="Input classification data to a CSV file. If the "
                                   "output file already exists, it will be opened and "
                                   "appended to. Press tab to autocomplete known species names.")

    p.add_argument("img_directory", help="the directory containing the images")
    p.add_argument("initials", help="your initials (use 'combined' to classify diffs of existing files)")
    p.add_argument("species_names", nargs='?', default=SPEC_FILE,
                   help="A list of additional species names for autocomplete "
                        "[default: '"+SPEC_FILE+"']")
    p.add_argument("--repro", action="store_true", help="Store proloculous data.")
    p.add_argument("--filter", action="store_true", help="Only update certain species of existing file")

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
    def __init__(self, img_dir, initials, repro=False, filt=False):

        self.img_dir = img_dir
        self.img_files = None
        self.get_img_files(self.img_dir)

        if not self.img_files:
            raise FileNotFoundError("no .jpg images found in directory {}".format(img_dir))

        self.sample = self.img_files[0].split('_')[0]
        self.f = join(self.img_dir, self.sample+"_species_"+initials+".csv")

        self.data = {}              # will be dict of obj -> (species, confidence)
        self.fdata = None           # data from other files, if initials == 'combined'
        self.known_species = set()
        self.lower_species = set()  # the species, in lowercase

        self.csv_headers = ['Sample Name', 'Obj. #', 'Species', 'Confidence']
        self.repro = repro
        self.filt = filt
        if repro:
            self.csv_headers.append('Proloculous')

        if isfile(self.f):
            print("Loading data from '{}'...".format(self.f))
            self._load_existing(self.f, self.data)
            print("Sample name: {}".format(self.sample))
            print("{} objects already in file.".format(len(self.data)))
        else:
            if filt:
                raise ValueError("filter option can only be used with an "
                                 "existing file")
            print("Generating new CSV file '{}'".format(self.f))

        # find diffs of previous files
        if initials == 'combined':
            self._find_agreements()

        self._species_filter = None
        if self.filt:
            self._get_species_filter()

        self.img_idx = 0

    def run(self):
        # start up the GUI
        self.display_proc = Popen([sys.executable, DISPLAY_FILE], stdin=PIPE)
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

    def _find_agreements(self):
        self.fdata = {}
        for csv_fname in iglob(join(self.img_dir, "*.csv")):
            if csv_fname == self.f:
                continue

            self.fdata[csv_fname] = {}
            self._load_existing(csv_fname, self.fdata[csv_fname], add_to_completer=False)

        shortest = min(self.fdata.values(), key=lambda x: len(x))
        for img_fname in shortest:
            # skip it if we already have it recorded
            if img_fname in self.data:
                continue

            # skip this image if one of the files didn't have it
            if not all(img_fname in self.fdata[k] for k in self.fdata):
                continue

            # add it to our data if everyone agreed
            if len(set(self.fdata[k][img_fname][0].lower().strip() for k in self.fdata)) > 1:
                continue

            # OK, if everyone agreed, add it to autocompleter
            spec = shortest[img_fname][0]
            self._register_species(spec)
            self.data[img_fname] = (spec, 3)

    def _get_species_filter(self):
        done = False
        self._species_filter = []
        print()
        print("Enter species to add to filter (tab complete enabled)")
        print("Press enter on blank entry when complete")
        while not done:
            spec = Completer(self.known_species).get_input("Species name: ")
            if not spec.strip():
                done = True
            else:
                self._species_filter.append(spec.strip().lower())

        confirm = 'a'
        while confirm.lower() not in 'yn':
            confirm = input("Confirm species filter list (y/n): ")

        if confirm == 'n':
            self._get_species_filter()  # try again

    def _load_existing(self, fname, data, add_to_completer=True):
        with open(fname, newline='') as csvfile:
            r = csv.reader(csvfile)

            try:
                header = next(r)
            except StopIteration:
                raise RuntimeError('file "{}" seems to be empty? delete it to '
                                   'have classifier make a new file'.format(fname)) from None

            # in case we are adding prolo data to existing file
            if header == self.csv_headers:
                in_repro = self.repro
            elif self.repro and header == self.csv_headers[:-1]:
                in_repro = False
            else:
                print(header)
                print(self.csv_headers)
                raise RuntimeError('first line of file does not match correct column labels')

            for row in r:
                if not in_repro:
                    name, obj, spec, conf = row
                    prolo = ''
                else:
                    name, obj, spec, conf, prolo = row

                if self.repro:
                    row_data = (spec, conf, prolo)
                else:
                    row_data = (spec, conf)

                try:
                    obj = int(obj)
                except ValueError:
                    err_str = "invalid object number '{}' in row {}".format(obj, len(data))
                    raise RuntimeError(err_str) from None

                if name != self.sample:
                    raise RuntimeError("File contains different sample names? '{}' and '{}' "
                                       "found".format(self.sample, name))

                img_fname = self.gen_filename(obj)
                obj_file = join(self.img_dir, img_fname)
                if not isfile(obj_file):
                    raise RuntimeError("No file '{}' found for object in CSV".format(obj_file))

                if add_to_completer:
                    self._register_species(spec)

                if img_fname in data:
                    raise ValueError("file '{}' found twice in data?".format(img_fname))

                data[img_fname] = row_data

    def _register_species(self, spec):
        if spec.lower() not in self.lower_species:
            self.lower_species.add(spec.lower())
            self.known_species.add(spec)

    def add_names_from_file(self, filename):
        with open(filename) as f:
            for line in f:
                self._register_species(line.strip())

    def _skip(self, idx):
        if self.img_idx >= len(self.img_files):
            return False

        fname = self.img_files[self.img_idx]
        if fname in self.data:
            if not self.repro:
                return True  # skip if we're not adding repro
            elif self.data[fname][-1] != '':
                return True

            if self._species_filter is not None:
                if self.data[fname][0].lower() not in self._species_filter:
                    return True

        return False

    def enter_data(self):
        while self._skip(self.img_idx):
            self.img_idx += 1

        if self.img_idx >= len(self.img_files):
            return False

        fname = self.img_files[self.img_idx]
        sample, obj = self.split_filename(fname)

        self.display_proc.stdin.write((join(self.img_dir, fname)+'\n').encode())
        self.display_proc.stdin.flush()

        if sample != self.sample:
            raise RuntimeError("Image has different sample name? '{}' and '{}' "
                               "found".format(self.sample, sample))

        print()
        print("Object number: {}".format(obj))

        if self.fdata is not None:
            print("Previous IDs:")
            for k in self.fdata:
                initials = basename(k).split('_')[2][:-4]
                if fname in self.fdata[k]:
                    ospec, oconf = self.fdata[k][fname]
                    print(" {}: {} (conf. {})".format(initials, ospec, oconf))
                else:
                    print(" {}: (not identified)".format(initials))

        if fname in self.data:
            spec, conf = self.data[fname][:2]
            print(f"Species: {spec}")
            print(f"Conf.: {conf}")
        else:
            spec = conf = None

        while spec is None:
            spec = Completer(self.known_species).get_input("Enter species name: ")
            spec = spec.strip()

            if spec == 'quit':
                return False

            conf = input("Confidence (1=low, 2=med, 3=high, c=change species): ")
            while conf not in ["1", "2", "3", "c"]:
                conf = input("Type 1, 2, or 3 for confidence: ")

            if conf == 'c':
                spec = None
                continue

            conf = int(conf)

        if self.repro:
            prolo = None
            while prolo not in ["mega", "micro", "unk", "c"]:
                prolo = input("Proloculous (mega, micro, unk, c=change species): ")

            # re-enter this species
            if prolo == 'c':
                del self.data[fname]
                return True

        self._register_species(spec)

        if not self.repro:
            self.data[fname] = (spec, conf)
        else:
            self.data[fname] = (spec, conf, prolo)
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
    c = Classifier(args.img_directory, args.initials, args.repro, args.filter)
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
