# Copyright 2022 Matusson
# Released under MIT License

from PySide2 import QtWidgets as qw, QtCore
import substance_painter.logging as lg
import substance_painter.project as pr
import substance_painter.event as ev
import substance_painter.textureset as ts
import substance_painter.js as js
import substance_painter.ui as ui
import json
import os


class ArchiverUI:
    def __init__(self):
        # Initialize the UI elements
        self.window = qw.QFrame()
        self.window.setWindowTitle("SPP Archiver")
        self.log = qw.QTextEdit()
        self.log.setReadOnly(True)
        self.left_button = qw.QPushButton()
        self.right_button = qw.QPushButton()
        self.autosaves_checkbox = qw.QCheckBox("Automatically delete autosaves")

        # Initialize layouts
        main_layout = qw.QVBoxLayout()
        button_layout = qw.QHBoxLayout()

        button_layout.addWidget(self.left_button)
        button_layout.addWidget(self.right_button)

        main_layout.addWidget(self.log)
        main_layout.addWidget(self.autosaves_checkbox)
        main_layout.addLayout(button_layout)
        self.window.setLayout(main_layout)

        # 0 - deciding if directory/project-only, 1 - confirming projects, 2 - currently in progress
        self.state = 0
        self.current_file = 0
        self.spp_files = []

        # Bind actions
        self.left_button.clicked.connect(self.left_clicked)
        self.right_button.clicked.connect(self.right_clicked)
        ev.DISPATCHER.connect(ev.ProjectEditionEntered, self.spp_loaded)

        self.send_ready_to_archive()
        self.update_buttons_text()
        ui.add_dock_widget(self.window)

    def __del__(self):
        ui.delete_ui_element(self.window)

    def left_clicked(self):
        # Select archive directory
        if self.state == 0:
            self.log.append("Scanning for .spp files...")
            directory = get_archiving_directory()

            # If cancelled
            if directory is None:
                return

            self.spp_files = get_spp_files(directory)
            self.log.append("----------------")

            # Make sure any files at all were found
            if len(self.spp_files) == 0 or self.spp_files is None:
                self.log.append("No .spp files were found.")
                return

            for file in self.spp_files:
                self.log.append(file)

            self.log.append("These files will be affected. Please review and confirm."
                            "\n*Painter might crash when done. This is normal and won't affect the outcome.")

            if len(self.spp_files) > 10:
                self.log.append("Archiving a lot of files can take a lof ot time!")

            # Files have been scanned, update the state
            self.state = 1
            self.update_buttons_text()
            return

        # Confirm directory archive
        if self.state == 1:
            # Update the UI
            self.state = 2
            self.update_buttons_text()

            self.spp_load_next()
            return

    def right_clicked(self):
        # Archive current project only
        if self.state == 0:
            if not pr.is_open():
                self.log.append("No project is open.")
                return

            # Templates have non-null paths, but can't be saved
            if pr.file_path() is None or pr.file_path() == "" or pr.file_path().endswith(".spt"):
                self.log.append("Save the project first.")
                return

            self.log.append("Archiving current project.")
            self.state = 2
            self.project_update_start()
            self.update_buttons_text()
            return

        # Cancel directory archive
        if self.state == 1:
            self.log.append("Cancelled.")
            self.state = 0

            self.send_ready_to_archive()
            self.update_buttons_text()
            return

    def spp_load_next(self):
        # Check if reached the end
        # This will inevitably crash when all files are processed, with no logs or messages or anything
        # This seems to be related to opening and closing the files in the same stack trace?
        # Can't confirm, couldn't fix in multiple hours, but it doesn't affect use.
        if self.current_file >= len(self.spp_files):
            self.reached_the_end()
            return

        if pr.is_open():
            pr.close()

        file = self.spp_files[self.current_file]
        while "_autosave_" in file and self.autosaves_checkbox.checkState():
            self.log.append("Removing {0}... (autosaved)".format(file))
            os.remove(file)
            self.current_file += 1

            # Check if reached the end
            if self.current_file == len(self.spp_files):
                self.reached_the_end()
                return

            file = self.spp_files[self.current_file]

        self.log.append("Opening {0}...".format(file))
        pr.open(file)

    def spp_loaded(self, e):
        if self.state is not 2:
            return

        self.log.append("Loaded.")
        self.project_update_start()

    def project_update_start(self):
        # Get and override the default baking parameters
        baking_parameters = js.evaluate("alg.baking.commonBakingParameters()")

        # But save the original to restore later
        orig_size = baking_parameters["commonParameters"]["Output_Size"]
        orig_aa = baking_parameters["detailParameters"]["Antialiasing"]

        baking_parameters["commonParameters"]["Output_Size"] = [1, 1]
        baking_parameters["detailParameters"]["Antialiasing"] = "None"

        js_set_code = "alg.baking.setCommonBakingParameters(JSON.parse('{0}'))".format(json.dumps(baking_parameters))
        js.evaluate(js_set_code)

        lg.log(lg.INFO, "SPP Archiver", "Updated baking parameters.")

        # Rebake all textures at very low resolution
        all_texture_sets = ts.all_texture_sets()
        for texset in all_texture_sets:
            lg.log(lg.INFO, "SPP Archiver", "Baking " + texset.name())

            js_bake_code = "alg.baking.bake('{0}')".format(texset)
            js.evaluate(js_bake_code)

        # Restore the settings
        baking_parameters["commonParameters"]["Output_Size"] = orig_size
        baking_parameters["detailParameters"]["Antialiasing"] = orig_aa
        js_set_code = "alg.baking.setCommonBakingParameters(JSON.parse('{0}'))".format(json.dumps(baking_parameters))
        js.evaluate(js_set_code)

        # Saving the finished result
        lg.log(lg.INFO, "SPP Archiver", "Finished baking, saving...")
        pr.save(pr.ProjectSaveMode.Full)

        self.project_update_finished()

    def project_update_finished(self):
        # In case of current-project-only archiving
        if len(self.spp_files) == 0:
            self.log.append("Finished archiving.")
            self.state = 0
            self.send_ready_to_archive()
            self.update_buttons_text()
            return

        self.log.append("Finished archiving {0}.".format(self.spp_files[self.current_file]))
        self.current_file += 1

        done_percent = (self.current_file / len(self.spp_files) * 100).__int__()
        self.log.append("{0}% done".format(done_percent))

        self.spp_load_next()
        return

    def reached_the_end(self):
        self.log.append("Finished archiving all files.")
        self.state = 0
        self.send_ready_to_archive()
        self.update_buttons_text()

    def send_ready_to_archive(self):
        message = "This tool re-bakes all mesh maps to just 2x2 resolution to save storage. " \
                  "You can always re-bake when necesary, " \
                  "however this can be a long process, so please use this tool cautiously.\n" \
                  "You can either archive all .spp files in a directory (and child directories), or just the " \
                  "currently open project.\nPlease select the appropriate option."
        self.log.append(message)

    def update_buttons_text(self):
        if self.state == 0:
            self.left_button.setText("Select directory...")
            self.right_button.setText("Current project only")

        if self.state == 1:
            self.left_button.setText("Confirm")
            self.right_button.setText("Cancel")

        if self.state == 2:
            self.left_button.setText("Please wait...")
            self.right_button.setText("Please wait...")


widget = None


def start_plugin():
    start_ui()


def start_ui():
    global widget
    widget = ArchiverUI()


def get_archiving_directory():
    archive_directory = qw.QFileDialog.getExistingDirectory(
        ui.get_main_window(), "Choose the archiving directory")
    if not archive_directory:
        # Cancelled
        return None

    return archive_directory


def get_spp_files(directory: str):
    spp_files = []

    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith('.spp'):
                spp_files.append(os.path.join(root, file))

    return spp_files


def close_plugin():
    global widget
    del widget


if __name__ == "__main__":
    start_plugin()
