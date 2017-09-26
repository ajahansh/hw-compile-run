from PyQt5 import QtCore
import os
import shutil
import zipfile


class ZipHandle(QtCore.QThread):
    """ This class should verify if the zip files are:
    1- Valid
    2- Properly structured, if not correct if possible
    3- clean the output
    All the outputs are sent to the console in the main program
    """
    log_trigger = QtCore.pyqtSignal(str)
    hw_add_trigger = QtCore.pyqtSignal(str)

    # root is the directory where zip_files are
    def __init__(self, root, zip_files, hw_re):
        QtCore.QThread.__init__(self)
        self.root = root
        self.files = zip_files
        self.hw_re = hw_re
        self.tmp_path = os.path.join(root, "zip_tmp")  # working on zip files

    def run(self):
        for zip_file in self.files:
            # Check if we have a valid zip file
            if self.zip_is_valid(zip_file) is False:  # zip is not valid
                continue  # ignore this file, error is reported in zip_is_valid
            self.zip_extract(zip_file)  # extract the zip contents to tmp_path

            # update folder structure of zip_file extracted in self.tmp_path
            if self.update_structure(zip_file):  # zip_file is in self.tmp_path
                self.make_clean(zip_file)  # delete .o and .exe files
                self.move_hw(zip_file)  # bring from self.tmp_path to self.root
                self.hw_add_trigger.emit(zip_file[:-4])  # signal the added hw

    def update_structure(self, zip_file):
        """ discover contents and retrieve files and folders, also
            correct the mistakes in the folder structure"""
        hw_ls = os.listdir(self.tmp_path)  # only 1 zip file is extracted here
        hw_dirs = [d for d in hw_ls if
                   os.path.isdir(os.path.join(self.tmp_path, d))]
        hw_files = [f for f in hw_ls if
                    os.path.isfile(os.path.join(self.tmp_path, f))]

        if len(hw_dirs) == 1 and len(hw_files) == 0:
            """ only 1 folder, with no (report) files, quite possibly the
                student has put everything in a parent folder. Check if the
                folder name does not comply with the format. Note that the
                zip filename is already checked and is correct. """
            self.rename_if_wrong(zip_file, hw_dirs[0])

        elif len(hw_dirs) == 2 and "__MACOSX" in hw_dirs and len(hw_files) == 0:
            # 2 root folders, the extra one is coming from MAC somehow
            shutil.rmtree(os.path.join(self.tmp_path, "__MACOSX"),
                          ignore_errors=True)
            hw_dirs.remove("__MACOSX")
            self.log(zip_file, "__MACOSX folder deleted.")
            self.rename_if_wrong(zip_file, hw_ls[0])  # might be badly named

        # The hw files and folders have no root folder, create one and move stuff
        else:
            path = os.path.join(self.tmp_path, zip_file[:-4])
            # In rare cases the hw folder might have another folder with the
            # same name. This is checked and an error is parsed
            if os.path.exists(path):  # ???
                self.log(zip_file, "Wrong folder structure: {}".format(path))
                return False
            else:
                # make parent folder and move everything inside
                os.mkdir(path)  # path does not exist for sure
                self.log(zip_file, "Parent folder {} Created".format(
                    zip_file[:-4]))
                for f in hw_files:  # move all the files
                    shutil.move(os.path.join(self.tmp_path, f), path)
                for d in hw_dirs:  # then move directories
                    shutil.move(os.path.join(self.tmp_path, d), path)
                for item in hw_ls:  # neither file nor directory ?
                    if item not in hw_dirs and item not in hw_files:
                        self.log(zip_file, "{}: neither file nor directory"
                                           ", ignored".format(item))
        # Now there should be just a parent folder with the right name
        assert len(os.listdir(self.tmp_path)) == 1
        return True

    def make_clean(self, zip_file):
        """ This function cleans the .o and .exe files, also removes spaces """
        path = os.path.join(self.tmp_path, os.listdir(self.tmp_path)[0])
        for root, _, file_names in os.walk(path):
            for file_name in file_names:
                f = file_name.lower()
                if f.endswith(".o"):
                    os.remove(os.path.join(root, file_name))
                elif f.endswith(".exe"):
                    os.remove(os.path.join(root, file_name))
                elif f.endswith("~"):
                    os.remove(os.path.join(root, file_name))
                elif f.endswith("#") and file_name.startswith("#"):
                    os.remove(os.path.join(root, file_name))
                elif ' ' in f:  # replace space with underline
                    os.rename(os.path.join(root, file_name),
                              os.path.join(root, file_name.replace(' ', '_')))

    def move_hw(self, zip_file):
        """ Move HW from tmp_path to root folder """
        hw_folder = os.listdir(self.tmp_path)[0]  # There is 1 folder only
        assert hw_folder == zip_file[:-4]  # just to check the folder name
        hw_path = os.path.join(self.tmp_path, hw_folder)
        if os.path.exists(os.path.join(self.root, hw_folder)):
            shutil.rmtree(os.path.join(self.root, hw_folder))  # in previous run
        shutil.move(hw_path, self.root)  # move the
        shutil.rmtree(self.tmp_path)  # tmp_path itself is also deleted

    def rename_if_wrong(self, zip_file, hw_folder_name):
        """ Check if the only root folder in zip_file complies with the format,
            if not, rename the folder from the main zip file."""
        hw_m = self.hw_re.match(hw_folder_name)
        if hw_m is None:  # 1 folder, but the name is wrong
            os.rename(os.path.join(self.tmp_path, hw_folder_name),
                      os.path.join(self.tmp_path, zip_file[:-4]))
            self.log(zip_file, "root: {} -> {}".format(hw_folder_name,
                                                       zip_file[:-4]))
        else:  # hw_root_folder matches the format
            pass

    def zip_extract(self, zip_file):
        # create a temp folder to store the zip contents
        if os.path.exists(self.tmp_path):  # from previous zip file
            shutil.rmtree(self.tmp_path, ignore_errors=True)
        os.mkdir(self.tmp_path)
        zip_path = os.path.join(self.root, zip_file)
        with zipfile.ZipFile(zip_path, 'r') as f:
            f.extractall(self.tmp_path)
            self.log_trigger.emit("{}: Extracting...".format(zip_file))

    def zip_is_valid(self, zip_file):
        zip_path = os.path.join(self.root, zip_file)
        if zipfile.is_zipfile(zip_path) is not True:  # Not valid zip file
            self.log(zip_file, "Corrupted. Can not unzip")
            return False
        elif self.hw_re.match(zip_file[:-4]) is None:
            self.log(zip_file, "Wrong name, correct and retry.")
            return False
        return True

    def log(self, zip_file, msg):
        self.log_trigger.emit("{}: {}".format(zip_file, msg))
