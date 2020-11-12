import tkinter as tk
from PIL import Image, ImageTk
import threading

class Display:

    def __init__(self, fname):
        self.fname = fname

        self.root = tk.Tk()
        self.root.title(self.fname)

        self.panel = tk.Label(self.root, image=self._get_tk_img(self.fname))
        self.panel.pack(side="bottom", fill="both", expand="yes")

        self.root.bind("<<update_event>>", self.eventhandler)  # event triggered by background thread
        self.root.bind("<<done_event>>", self.destroy)

    def run(self):
        self.root.mainloop()

    def destroy(self, state=None):
        self.root.destroy()

    def _get_tk_img(self, filename):
        self.pil_img = Image.open(filename)
        self.tk_img = ImageTk.PhotoImage(self.pil_img)
        return self.tk_img

    def eventhandler(self, state=None):
        self.root.title(self.fname)
        self.panel.configure(image=self._get_tk_img(self.fname))
        self.root.update()
