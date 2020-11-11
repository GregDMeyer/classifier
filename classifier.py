
from argparse import ArgumentParser
from os.path import isfile, join, split
import csv
import readline

# this doesn't work because of syntax errors :(
from sys import version_info
if version_info.major != 3:
    raise RuntimeError("classifier.py requires Python 3.")

SPEC_FILE = join(split(__file__)[0], 'default_species.txt')

def parse_args():
    p = ArgumentParser(description="Input classification data to a CSV file. If the "
                                   "output file already exists, it will be opened and "
                                   "appended to. Press tab to autocomplete known species names.")

    p.add_argument("csvfile", help="The output CSV file")
    p.add_argument("species_names", nargs='?', default=SPEC_FILE,
                   help="A list of additional species names for autocomplete "
                        "[default: 'default_species.txt']")

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
    def __init__(self, filename):

        self.sample = None
        self.data = []              # will be list of tuples of (species, confidence)
        self.known_species = set()
        self.lower_species = set()  # the species, in lowercase
        
        self.csv_headers = ['Sample Name', 'Obj. #', 'Species', 'Confidence']
        
        self.f = filename
        if isfile(self.f):
            print("Loading data from '{}'...".format(self.f))
            self._load_existing()
            print("Sample name: {}".format(self.sample))
            print("{} objects already in file.".format(len(self.data)))
        else:
            print("Generating new CSV file '{}'".format(self.f))
            self._init_fields()

    def _load_existing(self):
        with open(self.f, newline='') as csvfile:
            r = csv.reader(csvfile)

            try:
                header = next(r)
            except StopIteration:
                raise RuntimeError('file "" seems to be empty? delete it to '
                                   'have classifier make a new file')

            if header != self.csv_headers:
                print(header, self.csv_headers)
                raise RuntimeError('first line of file does not match correct column labels')

            for name, obj, spec, conf in r:
                try:
                    obj = int(obj)
                except ValueError:
                    err_str = "invalid object number '{}' in row {}".format(obj, len(self.data))
                    raise RuntimeError(err_str) from None

                # first row
                if self.sample is None:
                    self.sample = name
                    if obj != 1:
                        raise RuntimeError("object numbers in file do not start at 1")                        
                    
                if name != self.sample:
                    raise RuntimeError("File contains different sample names? '{}' and '{}' "
                                       "found".format(self.sample, name))
            
                if obj != len(self.data) + 1:
                    raise RuntimeError("Object numbers not in order? "
                                       "Went from {} to {}".format(len(self.data), obj))

                self._register_species(spec)
                self.data.append((spec, conf))
        
            if self.sample is None:
                self._init_fields()   # we didn't get a sample name because file had no rows

    def _init_fields(self):
        self.sample = input("Enter sample name: ")

    def _register_species(self, spec):
        if spec.lower() not in self.lower_species:
            self.lower_species.add(spec.lower())
            self.known_species.add(spec)
        
    def add_names_from_file(self, filename):
        with open(filename) as f:
            for line in f:
                self._register_species(line.strip())

    def enter_data(self):
        print()
        print("Object number: {}".format(len(self.data)+1))

        spec = Completer(self.known_species).get_input("Enter species name: ")
        self._register_species(spec)

        conf = input("Confidence (1=low, 2=med, 3=high): ")
        while conf not in ["1", "2", "3"]:
            conf = input("Type 1, 2, or 3 for confidence: ")
        conf = int(conf)

        self.data.append((spec, conf))
        self._write_file()

    def _write_file(self):
        with open(self.f, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(self.csv_headers)
            for i, val in enumerate(self.data):
                writer.writerow([self.sample, str(i+1).zfill(5)] + list(val))

                
class Completer:
    def __init__(self, options):
        self.options = options
        self.matches = None

    def complete(self, text, state):
        if state == 0:
            if text:
                self.matches = [s for s in self.options
                                if text.lower() in s.lower()]
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
    print('Press tab to autocomplete species names; type Ctrl+C to quit.')
    print('The file is saved every time a new object is entered.')
    print()

    c = None
    try:
        c = Classifier(args.csvfile)
        if args.species_names is not None:
            c.add_names_from_file(args.species_names)

        while True:
            c.enter_data()
    except KeyboardInterrupt:
        pass

    print()
    print()
    if c is None or not c.data:
        print('No objects recorded, file not written. Goodbye!')
    else:
        print('{} objects written to file. Goodbye!'.format(len(c.data)))

if __name__ == '__main__':
    main()
