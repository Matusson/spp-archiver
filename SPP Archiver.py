# Copyright 2026 Matelemons
# Released under MIT License
# Version 1.1.0


import substance_painter.logging as lg
import substance_painter.project as pr
import substance_painter.event as ev
import substance_painter.textureset as ts
import substance_painter.baking as bk
import substance_painter.ui as ui
import os

from PySide6 import QtWidgets as qw, QtCore


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
        self.modify_resolution_checkbox = qw.QCheckBox("Modify texture set resolution (128x128)")
        self.modify_resolution_checkbox.setChecked(True)  # Default to checked

        # Initialize layouts
        main_layout = qw.QVBoxLayout()
        button_layout = qw.QHBoxLayout()

        button_layout.addWidget(self.left_button)
        button_layout.addWidget(self.right_button)

        main_layout.addWidget(self.log)
        main_layout.addWidget(self.autosaves_checkbox)
        main_layout.addWidget(self.modify_resolution_checkbox)
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
        ev.DISPATCHER.connect(ev.BakingProcessEnded, self.baking_finished)

        # Track texture sets to bake and saved parameters
        self.texture_sets_to_bake = []
        self.current_texture_set_index = 0
        self.saved_parameters = {}

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

            self.log.append("These files will be affected. Please review and confirm.")

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
        if self.state != 2:
            return

        self.log.append("Loaded.")
        self.project_update_start()

    def project_update_start(self):
        # Get all texture sets to bake
        self.texture_sets_to_bake = ts.all_texture_sets()
        self.current_texture_set_index = 0
        self.saved_parameters = {}

        if len(self.texture_sets_to_bake) == 0:
            lg.log(lg.INFO, "SPP Archiver", "No texture sets to bake.")
            self.project_update_finished()
            return

        # Unlink all common parameters so we can modify each texture set independently
        bk.unlink_all_common_parameters()
        lg.log(lg.INFO, "SPP Archiver", "Unlinked common parameters.")

        # Start baking the first texture set
        self.bake_next_texture_set()

    def bake_next_texture_set(self):
        if self.current_texture_set_index >= len(self.texture_sets_to_bake):
            # All texture sets baked, restore settings
            self.restore_all_settings()
            lg.log(lg.INFO, "SPP Archiver", "All baking complete. Saving project...")

            # Use QTimer to delay save slightly so Painter isn't busy
            QtCore.QTimer.singleShot(500, self.save_and_finish)
            return

        texture_set = self.texture_sets_to_bake[self.current_texture_set_index]
        lg.log(lg.INFO, "SPP Archiver", "Baking " + texture_set.name)

        # Get baking parameters for this texture set
        baking_params = bk.BakingParameters.from_texture_set(texture_set)
        common_params = baking_params.common()

        # Save original values
        output_size_prop = common_params.get("OutputSize")

        if output_size_prop is not None:
            # Save original baking parameters (texture set resolution changes are permanent)
            self.saved_parameters[texture_set.name] = {
                "output_size": output_size_prop.value(),
                "enabled_bakers": baking_params.get_enabled_bakers(),
                "textureset_enabled": baking_params.is_textureset_enabled()
            }

            # Enable the texture set for baking
            baking_params.set_textureset_enabled(True)

            # Enable all bakers (mesh maps) for this texture set
            enabled_bakers = baking_params.get_enabled_bakers()
            if not enabled_bakers:
                # If no bakers enabled, enable common ones
                baking_params.set_enabled_bakers([
                    bk.MeshMapUsage.Normal,
                    bk.MeshMapUsage.WorldSpaceNormal,
                    bk.MeshMapUsage.ID,
                    bk.MeshMapUsage.AO,
                    bk.MeshMapUsage.Curvature,
                    bk.MeshMapUsage.Position,
                    bk.MeshMapUsage.Thickness
                ])

            # Set to low resolution
            bk.BakingParameters.set({output_size_prop: (1, 1)})
            lg.log(lg.INFO, "SPP Archiver", "Set baking resolution to 2x2 for " + texture_set.name)

            # Modify texture set resolution if checkbox is checked
            if self.modify_resolution_checkbox.isChecked():
                texture_set.set_resolution(ts.Resolution(128, 128))
                lg.log(lg.INFO, "SPP Archiver", "Set texture set resolution to 128x128 for " + texture_set.name)

        # Start async baking
        bk.bake_async(texture_set)

    def save_and_finish(self):
        try:
            # Use Full mode to create the smallest possible file
            pr.save(pr.ProjectSaveMode.Full)
            lg.log(lg.INFO, "SPP Archiver", "Project saved successfully")
        except Exception as e:
            lg.log(lg.ERROR, "SPP Archiver", "Failed to save project: " + str(e))

        self.project_update_finished()

    def baking_finished(self, event):
        # Only process if we're in archiving state
        if self.state != 2:
            return

        lg.log(lg.INFO, "SPP Archiver", "Baking completed for texture set.")

        # Move to next texture set
        self.current_texture_set_index += 1
        self.bake_next_texture_set()

    def restore_all_settings(self):
        # Restore original baking settings for all texture sets
        # Note: Texture set resolution changes are permanent and NOT restored
        for texture_set in self.texture_sets_to_bake:
            if texture_set.name in self.saved_parameters:
                saved = self.saved_parameters[texture_set.name]
                baking_params = bk.BakingParameters.from_texture_set(texture_set)
                common_params = baking_params.common()

                # Restore output size
                output_size_prop = common_params.get("OutputSize")
                if output_size_prop is not None:
                    bk.BakingParameters.set({output_size_prop: saved["output_size"]})

                # Restore enabled bakers and texture set state
                baking_params.set_enabled_bakers(saved["enabled_bakers"])
                baking_params.set_textureset_enabled(saved["textureset_enabled"])


        lg.log(lg.INFO, "SPP Archiver", "Restored baking settings.")

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
                  "In addition, the tool can further reduce storage by (permanently) changing texture set resolution and removing autosaves.\n" \
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
