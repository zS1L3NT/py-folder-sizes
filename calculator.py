from threading import Thread
from database import Database
from typing import Callable
import os

# path: "C:/Codes/py-folder-size/calculator.py"
# dir : ["C:", "Codes", "py-folder-size", "calculator.py"]
# name: "calculator.py"

class Calculator():
    def __init__(self, origin_path: str, database: Database):
        self.origin_path = origin_path
        self.database = database
        self.folders_done = []
        self.cancelled = False
        self.callback = lambda : None

        threads: list[FolderThread] = []

        for entity_name in os.listdir(self.origin_path):
            entity_path = f'{self.origin_path}/{entity_name}'
            if os.path.isdir(entity_path):
                i = len(self.folders_done)
                self.folders_done.append(False)
                threads.append(FolderThread(self, entity_path, i))

            if os.path.isfile(entity_path):
                self.set_file_size(entity_path, os.path.getsize(entity_path))

        for thread in threads: thread.start()

    def threads_done(self):
        self.database.update_completed(self.origin_path.split("/"))

        if self.callback is not None:
            self.callback()
    
    def cancel(self, callback: Callable):
        self.callback = callback
        self.cancelled = True

    def set_file_size(self, file_path: str, size: int) -> None:
        file_dir = file_path.split('/')

        self.database.set_ref(file_dir, size)
        file_dir.pop()
        self.database.add_size(file_dir, size)
        
        if "/".join(file_path.split("/")[:-1]) == self.origin_path:
            return
    
        origin_dir = self.origin_path.split("/")
        self.database.add_size(origin_dir, size)

    def set_folder_size(self, folder_path: str, size: int, completed: bool):
        folder_dir = folder_path.split('/')
        self.database.add_size(folder_dir, size)
        if completed:
            self.database.set_completed(folder_dir)

    def set_pause_position(self, folder_path: str):
        folder_dir = folder_path.split('/')
        folder_dir.pop()

        self.database.pause(folder_dir, folder_path)

class FolderThread():
    def __init__(self, parent: Calculator, folder_path: str, i: int):
        self.parent = parent
        self.folder_path = folder_path
        self.i = i
        self.callback_ran = False

    def start(self):
        thread = Thread(target=self.read_folder, args=(self.folder_path,))
        thread.start()

    def read_folder(self, folder_path: str) -> int:
        folder_size = 0

        (allowed, paused_path) = self.parent.database.read_clearance(folder_path.split("/"))
        
        for entity_name in os.listdir(folder_path):
            entity_path = f'{folder_path}/{entity_name}'
            entity_size = 0

            if not allowed:
                if entity_path == paused_path:
                    allowed = True
                else:
                    continue

            if self.parent.cancelled:
                self.parent.set_pause_position(entity_path)
                continue

            if os.path.isdir(entity_path):
                entity_size = self.read_folder(entity_path)

            if os.path.isfile(entity_path):
                entity_size = os.path.getsize(entity_path)
                self.parent.set_file_size(entity_path, entity_size)
            
            folder_size += entity_size
        
        self.parent.set_folder_size(folder_path, folder_size, not self.parent.cancelled)
        if self.folder_path != folder_path:
            return folder_size
        
        self.callback()
        
    def callback(self):
        if self.callback_ran: return
        self.callback_ran = True

        self.parent.folders_done[self.i] = True
        if all(self.parent.folders_done):
            self.parent.threads_done()
