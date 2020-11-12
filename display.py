import tkinter as tk
from PIL import Image, ImageTk
import threading

class Display:

    def __init__(self, fname):
        self.root = tk.Tk()
        self.root.title(fname)

        self.panel = tk.Label(self.root, image=self._get_tk_img(fname))
        self.panel.pack(side="bottom", fill="both", expand="yes")

    def destroy(self):
        self.root.destroy()

    def _get_tk_img(self, filename):
        self.pil_img = Image.open(filename)
        self.tk_img = ImageTk.PhotoImage(self.pil_img)
        return self.tk_img

    def update(self, fname):
        self.root.title(fname)
        self.panel.configure(image=self._get_tk_img(fname))
        self.root.update()
