#####################################################################
#                                                                   #
# __main__.py                                                       #
#                                                                   #
# Copyright 2014, Monash University                                 #
#                                                                   #
# This file is part of the program runviewer, in the labscript      #
# suite (see http://labscriptsuite.org), and is licensed under the  #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
import os
import labscript_utils.excepthook
from runviewer import APPLICATION_NAME, runviewer_dir

# Associate app windows with OS menu shortcuts:
import desktop_app
desktop_app.set_process_appid(APPLICATION_NAME)


# Splash screen
from labscript_utils.splash import Splash
splash = Splash(
    os.path.join(runviewer_dir, 'runviewer.svg'), application_name=APPLICATION_NAME
)
splash.show()

splash.update_text('importing standard library modules')
import sys
import time
import threading
from queue import Queue
import concurrent.futures
import traceback

splash.update_text('importing labscript suite modules')
from labscript_utils.setup_logging import setup_logging
logger = setup_logging(APPLICATION_NAME)
labscript_utils.excepthook.set_logger(logger)

splash.update_text('importing h5_lock and h5py')
import labscript_utils.h5_lock
import h5py

# No splash update for Qt - the splash screen already imported it
from qtutils.qt import QtCore, QtGui, QtWidgets

splash.update_text('importing pyqtgraph')
import pyqtgraph as pg

splash.update_text('importing numpy')
import numpy
splash.update_text('importing scipy')
from scipy import interpolate

pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')

from qtutils import UiLoader, inmain_decorator, inmain_later
import qtutils.icons
splash.update_text('importing labscript suite modules')
from labscript_utils.connections import ConnectionTable
from labscript_utils import device_registry, ensure_str

from labscript_utils.labconfig import (
    LabConfig,
    save_appconfig,
    load_appconfig,
)
from labscript_utils.qtwidgets.application import (
    LabscriptGuiApplication,
    exec_qapplication,
)
from labscript_utils.qtwidgets.leftclick import TreeView
from labscript_utils.qtwidgets.themed_window import ThemedWindow
from labscript_utils.ls_zprocess import ZMQServer, ProcessTree
import labscript_utils.qtwidgets.file_dialogs as file_dialogs
process_tree = ProcessTree.instance()
process_tree.zlock_client.set_process_name(APPLICATION_NAME)

from labscript_c_extensions.runviewer.resample import resample as _resample


SHOT_MODEL__COLOUR_INDEX = 0
SHOT_MODEL__SHUTTER_INDEX = 1
SHOT_MODEL__CHECKBOX_INDEX = 2
SHOT_MODEL__PATH_INDEX = 1
CHANNEL_MODEL__CHECKBOX_INDEX = 0
CHANNEL_MODEL__CHANNEL_INDEX = 0


def format_time(input_sec):
    # input_sec is in seconds
    if input_sec >= 1:
        return f"{input_sec:.3g}s"
    elif input_sec >= 1e-3:
        return f"{input_sec * 1e3:.3g}ms"
    elif input_sec >= 1e-6:
        return f"{input_sec * 1e6:.3g}us"
    elif input_sec >= 1e-9:
        return f"{input_sec * 1e9:.3g}ns"
    elif input_sec >= 1e-12:
        return f"{input_sec * 1e12:.3g}ps"
    elif input_sec >= 1e-15:
        return f"{input_sec * 1e15:.3g}fs"
    elif input_sec >= 1e-18:
        return f"{input_sec * 1e18:.3g}as"
    else:
        return str(input_sec) + "s"


def int_to_enum(enum_list, value):
    """Return the member of enum_list equal to value, which a model hands back as an int."""

    for item in enum_list:
        if item == value:
            return item
    return value


class ScaleHandler:

    def __init__(self, input_times, target_positions, stop_time):
        # Each of input_times maps to its target position, and times between them
        # are interpolated linearly.
        self.org_stop_time = float(stop_time)

        if not all((x >= 0) and (x <= self.org_stop_time) for x in input_times):
            raise Exception('shot contains at least one marker before t=0 and/or after the stop time. Non-linear time currently does not support this.')

        unscaled_times = sorted(input_times)
        scaled_times = sorted(target_positions)

        # append values for linear scaling before t=0 and after stop time
        unscaled_times = [min(unscaled_times)-1e-9] + unscaled_times + [max(unscaled_times) + 1e-9]
        scaled_times = [min(scaled_times)-1e-9] + scaled_times + [max(scaled_times) + 1e-9]

        self.get_scaled_time = interpolate.interp1d(unscaled_times, scaled_times, assume_sorted=True, bounds_error=False, fill_value='extrapolate')
        self.get_unscaled_time = interpolate.interp1d(scaled_times, unscaled_times, assume_sorted=True, bounds_error=False, fill_value='extrapolate')

        self.scaled_stop_time = self.get_scaled_time(self.org_stop_time)


class ColourDelegate(QtWidgets.QItemDelegate):

    def __init__(self, view, *args, **kwargs):
        QtWidgets.QItemDelegate.__init__(self, *args, **kwargs)
        self._view = view
        self._colours = [QtCore.Qt.black, QtCore.Qt.red, QtCore.Qt.green, QtCore.Qt.blue, QtCore.Qt.cyan, QtCore.Qt.magenta, QtCore.Qt.yellow, QtCore.Qt.gray, QtCore.Qt.darkRed, QtCore.Qt.darkGreen, QtCore.Qt.darkBlue, QtCore.Qt.darkCyan, QtCore.Qt.darkMagenta, QtCore.Qt.darkYellow, QtCore.Qt.darkGray, QtCore.Qt.lightGray]

        self._current_colour_index = 0

    def get_next_colour(self):
        colour = self._colours[self._current_colour_index]
        self._current_colour_index += 1
        if self._current_colour_index >= len(self._colours):
            self._current_colour_index = 0
        return colour

    def createEditor(self, parent, option, index):
        editor = QtWidgets.QComboBox(parent)
        for colour in self._colours:
            pixmap = QtGui.QPixmap(20, 20)
            pixmap.fill(colour)
            editor.addItem(QtGui.QIcon(pixmap), '', colour)

        editor.activated.connect(lambda index, editor=editor: self._view.commitData(editor))
        editor.activated.connect(lambda index, editor=editor: self._view.closeEditor(editor, QtWidgets.QAbstractItemDelegate.NoHint))
        QtCore.QTimer.singleShot(10, editor.showPopup)

        return editor

    def setEditorData(self, editor, index):
        value = index.model().data(index, QtCore.Qt.UserRole)
        for i in range(editor.count()):
            if editor.itemData(i) == value():
                editor.setCurrentIndex(i)
                break

    def setModelData(self, editor, model, index):
        icon = editor.itemIcon(editor.currentIndex())
        colour = editor.itemData(editor.currentIndex())

        # Note, all data being written to the model must be read out of the editor PRIOR to calling model.setData()
        #       This is because a call to model.setData() triggers setEditorData(), which messes up subsequent
        #       calls to the editor to determine the currently selected item/data
        model.setData(index, icon, QtCore.Qt.DecorationRole)
        model.setData(index, lambda clist=self._colours, colour=colour: int_to_enum(clist, colour), QtCore.Qt.UserRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


class RunviewerMainWindow(ThemedWindow, QtWidgets.QMainWindow):
    def __init__(self, app):
        super().__init__()
        self.app = app

    def closeEvent(self, event):
        if self.app.offer_to_save_changes('Quit runviewer', quitting=True):
            event.accept()
        else:
            event.ignore()


class RunViewer(LabscriptGuiApplication):
    app_name = 'runviewer'
    default_config_filename = 'runviewer.toml'
    geometry_keys = ('window_size', 'window_pos', 'splitter', 'splitter_2')

    def __init__(self, exp_config):
        splash.update_text('loading graphical interface')
        loader = UiLoader()
        loader.registerCustomWidget(TreeView)
        self.ui = loader.load(
            os.path.join(runviewer_dir, 'main.ui'), RunviewerMainWindow(self)
        )
        self.exp_config = exp_config
        self.init_config_window_title()

        # setup shot treeview model
        self.shot_model = QtGui.QStandardItemModel()
        self.shot_model.setHorizontalHeaderLabels(['colour', 'shutters', 'path'])
        self.ui.shot_treeview.setModel(self.shot_model)
        self.ui.shot_treeview.resizeColumnToContents(1)
        self.shot_model.itemChanged.connect(self.on_shot_selection_changed)
        self.shot_colour_delegate = ColourDelegate(self.ui.shot_treeview)
        self.ui.shot_treeview.setItemDelegateForColumn(0, self.shot_colour_delegate)

        # setup channel treeview model
        self.channel_model = QtGui.QStandardItemModel()
        self.channel_model.setHorizontalHeaderLabels(['channel'])
        self.ui.channel_treeview.setModel(self.channel_model)
        self.channel_model.itemChanged.connect(self.update_plots)

        # create a hidden plot widget that all plots can link their x-axis too
        hidden_plot = pg.PlotWidget(name='runviewer - time axis link')

        hidden_plot.setMinimumHeight(1)
        hidden_plot.setMaximumHeight(1)
        hidden_plot.setLabel('bottom', 'Time', units='s')
        hidden_plot.setLabel('left', " ")
        hidden_plot.showAxis('right', True)
        hidden_plot_item = hidden_plot.plot([0, 1], [0, 0])
        self._hidden_plot = (hidden_plot, hidden_plot_item)
        self.ui.hidden_plot_layout.addWidget(hidden_plot)

        time_axis_plot = pg.PlotWidget()
        time_axis_plot.setMinimumHeight(120)
        time_axis_plot.setMaximumHeight(120)
        time_axis_plot.setLabel('bottom', 'Time', units='s')
        time_axis_plot.showAxis('right', True)
        time_axis_plot.setXLink('runviewer - time axis link')
        time_axis_plot.setMouseEnabled(y=False)
        time_axis_plot.getAxis('left').setTicks([])  # hide y ticks in the left & right side. only show time axis
        time_axis_plot.getAxis('right').setTicks([])
        time_axis_plot.setLabel('left', 'Slots')
        time_axis_plot.scene().sigMouseMoved.connect(lambda pos: self.mouseMovedEvent(pos, time_axis_plot, "Slots"))
        time_axis_plot_item = time_axis_plot.plot([0, 1], [0, 0], pen=(255, 255, 255))
        self._time_axis_plot = (time_axis_plot, time_axis_plot_item)

        self.all_markers = {}
        self.all_marker_items = {}
        self.movable_marker_items = {}
        markers_plot = pg.PlotWidget(name='runviewer - markers')
        markers_plot.setMinimumHeight(120)
        markers_plot.setMaximumHeight(120)
        markers_plot.showAxis('top', False)
        markers_plot.showAxis('bottom', False)
        markers_plot.showAxis('left', True)
        markers_plot.showAxis('right', True)
        markers_plot.getAxis('left').setTicks([])
        markers_plot.getAxis('right').setTicks([])
        markers_plot.setLabel('left', 'Markers')
        markers_plot.setXLink('runviewer - time axis link')
        markers_plot.setMouseEnabled(y=False)
        markers_plot.scene().sigMouseMoved.connect(lambda pos: self.mouseMovedEvent(pos, markers_plot, "Markers"))
        markers_plot_item = markers_plot.plot([])
        self._markers_plot = (markers_plot, markers_plot_item)

        self.ui.verticalLayout_9.insertWidget(1,markers_plot)
        self.ui.plot_layout.addWidget(time_axis_plot)

        # add some icons
        self.ui.add_shot.setIcon(QtGui.QIcon(':/qtutils/fugue/plus'))
        self.ui.remove_shots.setIcon(QtGui.QIcon(':/qtutils/fugue/minus'))
        self.ui.enable_selected_shots.setIcon(QtGui.QIcon(':/qtutils/fugue/ui-check-box'))
        self.ui.disable_selected_shots.setIcon(QtGui.QIcon(':/qtutils/fugue/ui-check-box-uncheck'))
        self.ui.channel_move_to_top.setIcon(QtGui.QIcon(':/qtutils/fugue/arrow-stop-090'))
        self.ui.channel_move_up.setIcon(QtGui.QIcon(':/qtutils/fugue/arrow-090'))
        self.ui.channel_move_down.setIcon(QtGui.QIcon(':/qtutils/fugue/arrow-270'))
        self.ui.channel_move_to_bottom.setIcon(QtGui.QIcon(':/qtutils/fugue/arrow-stop-270'))
        self.ui.reset_x_axis.setIcon(QtGui.QIcon(':/qtutils/fugue/layer-resize-replicate'))
        self.ui.reset_y_axis.setIcon(QtGui.QIcon(':/qtutils/fugue/layer-resize-replicate-vertical'))
        self.ui.toggle_tooltip.setIcon(QtGui.QIcon(':/qtutils/fugue/ui-tooltip-balloon'))
        self.ui.linear_time.setIcon(QtGui.QIcon(':/qtutils/fugue/clock-history'))
        self.ui.equal_space_time.setIcon(QtGui.QIcon(':/qtutils/fugue/border-vertical-all'))

        self.ui.linear_time.setEnabled(False)
        self.ui.equal_space_time.setEnabled(False)

        self.ui.actionOpen_Shot.setIcon(QtGui.QIcon(':/qtutils/fugue/plus'))
        self.ui.actionQuit.setIcon(QtGui.QIcon(':/qtutils/fugue/cross-button'))
        self.ui.actionLoad_channel_config.setIcon(QtGui.QIcon(':/qtutils/fugue/folder-open'))
        self.ui.actionSave_channel_config.setIcon(QtGui.QIcon(':/qtutils/fugue/disk'))

        # connect signals
        self.ui.reset_x_axis.clicked.connect(self.on_x_axis_reset)
        self.ui.reset_y_axis.clicked.connect(self.on_y_axes_reset)
        channels = self.ui.channel_treeview
        self.ui.channel_move_up.clicked.connect(lambda: channels.move_selected_rows('up'))
        self.ui.channel_move_down.clicked.connect(
            lambda: channels.move_selected_rows('down')
        )
        self.ui.channel_move_to_top.clicked.connect(
            lambda: channels.move_selected_rows('top')
        )
        self.ui.channel_move_to_bottom.clicked.connect(
            lambda: channels.move_selected_rows('bottom')
        )
        channels.rowsReordered.connect(lambda order: self.update_plot_positions())
        self.ui.enable_selected_shots.clicked.connect(self._enable_selected_shots)
        self.ui.disable_selected_shots.clicked.connect(self._disable_selected_shots)
        self.ui.add_shot.clicked.connect(self.on_add_shot)
        self.ui.markers_comboBox.currentIndexChanged.connect(self._update_markers)
        self.ui.linear_time.clicked.connect(self._reset_linear_time)
        self.ui.equal_space_time.clicked.connect(self._space_markers_evenly)
        self.ui.remove_shots.clicked.connect(self.on_remove_shots)

        self.ui.actionOpen_Shot.triggered.connect(self.on_add_shot)
        self.ui.actionQuit.triggered.connect(self.ui.close)
        self.ui.actionLoad_configuration.triggered.connect(self.on_load_configuration_triggered)
        self.ui.actionRevert_configuration.triggered.connect(self.on_revert_configuration_triggered)
        self.ui.actionSave_configuration.triggered.connect(self.on_save_configuration_triggered)
        self.ui.actionSave_configuration_as.triggered.connect(self.on_save_configuration_as_triggered)
        self.ui.actionLoad_channel_config.triggered.connect(self.on_load_channel_config)
        self.ui.actionSave_channel_config.triggered.connect(self.on_save_channel_config)

        # Keyboard shortcuts:
        QtGui.QShortcut('Del', self.ui.shot_treeview, lambda: self.on_remove_shots(confirm=True))
        QtGui.QShortcut('Shift+Del', self.ui.shot_treeview, lambda: self.on_remove_shots(confirm=False))

        splash.update_text('done')
        self.ui.show()

        # internal variables
        self.plot_widgets = {}
        self.plot_items = {}
        self.shutter_lines = {}

        self.default_config_path = os.path.dirname(
            self.get_default_config_file(ensure_directory=True)
        )

        self.last_save_config_file = None
        self.last_save_data = None
        try:
            self.load_configuration(self.get_default_config_file())
        except Exception:
            logger.exception('Could not load the runviewer configuration')

        self.last_opened_shots_folder = exp_config.get('paths', 'experiment_shot_storage')

        # start resample thread
        self._resample = False
        self._thread = threading.Thread(target=self._resample_thread)
        self._thread.daemon = True
        self._thread.start()

        # start shots_to_process_queue monitoring thread
        self._shots_to_process_thread = threading.Thread(target=self._process_shots)
        self._shots_to_process_thread.daemon = True
        self._shots_to_process_thread.start()

        self.scale_time = False
        self.scalehandler = None

    def get_save_data(self):
        """Return the runviewer GUI state stored in TOML app config."""
        window_size = self.ui.size()
        window_pos = self.ui.pos()
        return {
            'window_size': [window_size.width(), window_size.height()],
            'window_pos': [window_pos.x(), window_pos.y()],
            'splitter': self.ui.splitter.sizes(),
            'splitter_2': self.ui.splitter_2.sizes(),
        }

    def load_configuration(self, filename):
        """Load runviewer GUI state from a TOML/legacy INI config file."""
        # LEGACY INI COMPATIBILITY. DEPRECATED CODE, WILL BE REMOVED.
        appconfig, save_target = load_appconfig(filename, return_save_path=True)
        save_data = appconfig.get('runviewer_state', {})
        # Saving the layout over a channel configuration on quitting would lose its
        # channels:
        if 'runviewer_channels' in appconfig or 'channels' in save_data:
            self.error_dialog(
                f'{filename} is a channel configuration; use Load channel config.'
            )
            return
        if 'window_size' in save_data:
            self.ui.resize(*save_data['window_size'])
        if 'window_pos' in save_data:
            self.ui.move(*save_data['window_pos'])
        if 'splitter' in save_data:
            self.ui.splitter.setSizes(save_data['splitter'])
        if 'splitter_2' in save_data:
            self.ui.splitter_2.setSizes(save_data['splitter_2'])
        self.last_save_config_file = save_target
        self.last_save_data = self.get_save_data()
        self.ui.actionSave_configuration.setText(f'Save configuration {save_target}')
        self.ui.actionSave_configuration_as.setEnabled(True)
        self.ui.actionRevert_configuration.setEnabled(True)
        self.set_config_window_title(save_target)

    def _update_markers(self, index):
        for line, plot in self.all_marker_items.items():
            plot.removeItem(line)
        self.all_marker_items = {}

        for line, plot in self.movable_marker_items.items():
            plot.removeItem(line)
        self.movable_marker_items = {}
        self.marker_times_unscaled = {}

        marker_index = self.ui.markers_comboBox.currentIndex()
        shot = self.ui.markers_comboBox.itemData(marker_index)

        if index == 0:
            self.ui.linear_time.setEnabled(False)
            self.ui.equal_space_time.setEnabled(False)
            self.all_markers = {}
        else:
            self.ui.linear_time.setEnabled(True)
            self.ui.equal_space_time.setEnabled(True)
            self.all_markers = shot.markers

        times = sorted(list(self.all_markers.keys()))
        last_time = 0
        for i, (t, m) in enumerate(sorted(self.all_markers.items())):
            if i < len(times)-1:
                delta_t = times[i+1] - t
            # Now always have a marker at stop time

            unscaled_t = t
            if self.scale_time:
                t = self.scalehandler.get_scaled_time(t)

            color = m['color']
            r, g, b = color
            if (r, g, b) == (-1, -1, -1):
                # Default colour, black:
                r, g, b = (0, 0, 0)
            color = QtGui.QColor(r, g, b)
            label = ensure_str(m['label'])
            if i == 0:
                line = self._markers_plot[0].addLine(x=t, pen=pg.mkPen(color=color, width=1.5, style=QtCore.Qt.DashLine), label=label, labelOpts= {"color": color, "fill": QtGui.QColor(255, 255, 255, 255), "rotateAxis":(1, 0), "anchors": [(0.5, 0),(0.5, 0)]}, movable=False )
            else:
                line = self._markers_plot[0].addLine(x=t, pen=pg.mkPen(color=color, width=1.5, style=QtCore.Qt.DashLine), label=label, labelOpts= {"color": color, "fill": QtGui.QColor(255, 255, 255, 255), "rotateAxis":(1, 0), "anchors": [(0.5, 0),(0.5, 0)]}, movable=True )
                line.setBounds([last_time+1e-9 if last_time !=0 else last_time ,None])
                line.sigPositionChanged.connect(self._marker_moving)
                line.sigPositionChangeFinished.connect(self._marker_moved)
            self.movable_marker_items[line] = self._markers_plot[0]
            self.marker_times_unscaled[line] = unscaled_t

            line = self._time_axis_plot[0].addLine(x=t, pen=pg.mkPen(color=color, width=1.5, style=QtCore.Qt.DashLine), label=format_time(delta_t), labelOpts= {"color": color, "fill": QtGui.QColor(255, 255, 255, 255), "rotateAxis":(1, 0), "anchors": [(0.5, 0),(0.5, 0)]}, movable=False )
            self.all_marker_items[line] = self._time_axis_plot[0]
            last_time = t
        self.update_plots()

    def mouseMovedEvent(self, position, ui, name):
        if self.ui.toggle_tooltip.isChecked():
            v = ui.scene().views()[0]
            viewP = v.mapFromScene(position)
            glob_pos = ui.mapToGlobal(viewP)  # convert to Screen x
            glob_zero = ui.mapToGlobal(QtCore.QPoint(0, 0))
            self._global_start_x = glob_zero.x()
            self._global_start_y = glob_zero.y()
            self._global_width = ui.width()
            self._global_height = ui.height()

            coord_pos = ui.plotItem.vb.mapSceneToView(position)

            if len(self.get_selected_shots_and_colours()) > 0:
                scaled_t = float(coord_pos.x())
                if self.scale_time and self.scalehandler is not None:
                    unscaled_t = float(self.scalehandler.get_unscaled_time(scaled_t))
                else:
                    unscaled_t = scaled_t
                if unscaled_t is not None:
                    pos = QtCore.QPoint(glob_pos.x(), glob_pos.y())
                    plot_data = ui.plotItem.listDataItems()[0].getData()
                    if plot_data[0] is not None and scaled_t is not None:
                        nearest_index = numpy.abs(plot_data[0] - scaled_t).argmin() - 1
                        y_val = f'{plot_data[1][nearest_index]:.2f}'
                    else:
                        y_val = '-'
                    text = f'Plot: {name} \nTime: {unscaled_t:.9f}s\nValue: {y_val}'
                    QtWidgets.QToolTip.showText(pos, text)

    def _reset_linear_time(self):
        self.scale_time = False
        markers_unscaled = sorted(list(self.all_markers.keys()))
        marker_index = self.ui.markers_comboBox.currentIndex()
        shot = self.ui.markers_comboBox.itemData(marker_index)
        scalehandler = ScaleHandler(markers_unscaled, markers_unscaled, shot.stop_time)
        self._update_non_linear_time(new_scalehandler=scalehandler)
        self.on_x_axis_reset()
        self._resample = True

    def _space_markers_evenly(self):
        self.scale_time = True
        marker_index = self.ui.markers_comboBox.currentIndex()
        shot = self.ui.markers_comboBox.itemData(marker_index)
        markers_unscaled = sorted(list(self.all_markers.keys()))
        target_length = shot.stop_time / float(len(markers_unscaled) - 1)
        scaled_times = [target_length * i for i in range(len(markers_unscaled))]
        scalehandler = ScaleHandler(markers_unscaled, scaled_times, shot.stop_time)
        self._update_non_linear_time(new_scalehandler=scalehandler)
        self.on_x_axis_reset()
        self._resample = True

    def _marker_moving(self, line):
        self.scale_time = True
        marker_index = self.ui.markers_comboBox.currentIndex()
        shot = self.ui.markers_comboBox.itemData(marker_index)
        markers_unscaled = sorted(list(self.all_markers.keys()))

        # What was the unscaled time of the marker that moved, and where is it now?
        moved_marker_unscaled_t = self.marker_times_unscaled[line]
        moved_marker_new_pos = line.pos().x()

        # Where was the marker just before it was moved? This is given by the current scalehandler
        if self.scalehandler is not None:
            moved_marker_last_pos = self.scalehandler.get_scaled_time(moved_marker_unscaled_t)
        else:
            moved_marker_last_pos = moved_marker_unscaled_t

        # How far has the marker moved?
        delta_marker = moved_marker_new_pos - moved_marker_last_pos

        # Now we want to shift the other markers if the are at a higher position than this one
        markers = list(self.marker_times_unscaled.keys())
        new_scaled_times = []
        for marker in markers:
            if marker == line:
                new_scaled_times.append(moved_marker_new_pos)
            else:
                x = marker.pos().x()

                if x > moved_marker_last_pos:
                    x += delta_marker
                new_scaled_times.append(x)
        new_scaled_times = sorted(new_scaled_times)
        scalehandler = ScaleHandler(markers_unscaled,new_scaled_times, shot.stop_time)
        self._update_non_linear_time(new_scalehandler=scalehandler)

    def _marker_moved(self, line):
        self._resample = True

    def _update_non_linear_time(self, changed_shot=False, new_scalehandler=None):

        marker_index = self.ui.markers_comboBox.currentIndex()
        shot = self.ui.markers_comboBox.itemData(marker_index)
        if new_scalehandler is None:
            # make a 1:1 scalehandler using the hidden_plot
            self.scale_time = False
            end_t = self._hidden_plot[1].getData()[0][-1]
            new_scalehandler = ScaleHandler([0,end_t],[0,end_t],end_t)

        old_scalehandler = self.scalehandler
        self.scalehandler = new_scalehandler

        # combine markers and shutter lines
        markers = list(self.all_marker_items.keys())
        for channel in self.shutter_lines:
            for shot in self.shutter_lines[channel]:
                for line in self.shutter_lines[channel][shot][0]:
                    markers.append(line)
                for line in self.shutter_lines[channel][shot][1]:
                    markers.append(line)

        # Move all Markes/Shutter Lines to new position
        for marker in markers:
            pos = marker.pos()

            if old_scalehandler is None:
                unscaled_x = pos.x()
            else:
                unscaled_x = old_scalehandler.get_unscaled_time(pos.x())

            if self.scale_time and self.scalehandler is not None:
                new_x = self.scalehandler.get_scaled_time(unscaled_x)
            else:
                new_x = unscaled_x

            pos.setX(new_x)
            marker.setPos(pos)

        # Move the movable lines in the upper graph
        mv_markers = list(self.movable_marker_items.keys())
        new_marker_times = {}
        for marker in mv_markers:
            if self.scale_time and self.scalehandler is not None:
                new_x = self.scalehandler.get_scaled_time(self.marker_times_unscaled[marker])
            else:
                new_x = self.marker_times_unscaled[marker]

            new_marker_times[float(new_x)] = marker

        last_time = None
        for t in sorted(list(new_marker_times.keys())):
            marker = new_marker_times[t]
            marker.blockSignals(True)
            marker.setBounds([None, None])
            marker.setPos(t)
            marker.setBounds([last_time+1e-9 if last_time is not None else 0.0, None])
            marker.blockSignals(False)
            last_time = t

        if shot is not None and self.scale_time:
            self._time_axis_plot[0].getAxis("bottom").setTicks([[[0, str(0)], [shot.stop_time, str(shot.stop_time)]]])
            for plot in self.plot_widgets.values():
                plot.getAxis("bottom").setTicks([[[0, str(0)], [shot.stop_time, str(shot.stop_time)]]])
        else:
            self._time_axis_plot[0].getAxis("bottom").setTicks(None)
            for plot in self.plot_widgets.values():
                plot.getAxis("bottom").setTicks(None)

        for plot in self.plot_widgets.values():
            for item in plot.getPlotItem().items:
                if isinstance(item, pg.PlotDataItem):
                    if old_scalehandler is not None:
                        unscaled_t = old_scalehandler.get_unscaled_time(item.xData)
                    else:
                        unscaled_t = item.xData

                    if self.scalehandler is not None:
                        item.setData(self.scalehandler.get_scaled_time(unscaled_t), item.yData)
                    else:
                        item.setData(unscaled_t, item.yData)

    def _process_shots(self):
        while True:
            filepath = shots_to_process_queue.get()
            inmain_later(self.load_shot, filepath)

    def on_load_channel_config(self):
        # LEGACY INI COMPATIBILITY. DEPRECATED CODE, WILL BE REMOVED.
        config_file = file_dialogs.open_file(
            self.ui,
            "Select file to load",
            self.default_config_path,
            "Config files (*.toml *.ini)",
        )
        if config_file:
            # LEGACY INI COMPATIBILITY. DEPRECATED CODE, WILL BE REMOVED.
            appconfig = load_appconfig(config_file)
            # Channel configurations saved before they had their own table:
            channels = appconfig.get(
                'runviewer_channels', appconfig.get('runviewer_state', {})
            ).get('channels', [])

            for row, (channel, checked) in enumerate(channels):
                check_items = self.channel_model.findItems(channel)
                if len(check_items) == 0:
                    items = []
                    check_item = QtGui.QStandardItem(channel)
                    check_item.setEditable(False)
                    check_item.setCheckable(True)
                    items.append(check_item)
                    check_item.setCheckState(QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked)
                    check_item.setEnabled(False)
                    self.channel_model.insertRow(row, items)
                else:
                    check_item = check_items[0]
                    check_item.setCheckState(QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked)
                    self.channel_model.takeRow(check_item.row())
                    self.channel_model.insertRow(row, check_item)

    def on_save_channel_config(self):
        # A file name keeps '.toml', where a bare folder lets the macOS panel choose
        # an extension. 'untitled' is not the state file, which shares the folder.
        suggested_file = os.path.join(self.default_config_path, 'untitled.toml')
        save_file = file_dialogs.save_file(
            self.ui,
            'Select  file to save current channel configuration',
            suggested_file,
            "Config files (*.toml)",
        )
        if save_file:
            channels = []
            for row in range(self.channel_model.rowCount()):
                item = self.channel_model.item(row)
                channels.append((item.text(), item.checkState() == QtCore.Qt.Checked))

            save_appconfig(save_file, {'runviewer_channels': {'channels': channels}})

    def on_toggle_shutter(self, checked, current_shot):
        for channel in self.shutter_lines:
            for shot in self.shutter_lines[channel]:
                if shot == current_shot:
                    for line in self.shutter_lines[channel][shot][0]:
                        if checked:
                            line.show()
                        else:
                            line.hide()
                    for line in self.shutter_lines[channel][shot][1]:
                        if checked:
                            line.show()
                        else:
                            line.hide()

    def on_add_shot(self):
        selected_files = file_dialogs.open_files(
            self.ui,
            "Select file to load",
            self.last_opened_shots_folder,
            "HDF5 files (*.h5 *.hdf5)",
        )
        if not selected_files:
            return
        popup_warning = False
        self.last_opened_shots_folder = os.path.dirname(selected_files[0])

        for file in selected_files:
            try:
                filepath = str(file)
                # The dialog accepts a typed name that its filter excludes:
                if filepath.endswith('.h5') or filepath.endswith('.hdf5'):
                    self.load_shot(filepath)
                else:
                    popup_warning = True
            except:
                popup_warning = True
                raise
        if popup_warning:
            self.error_dialog(
                'Some shots were not loaded because they were not valid hdf5 files'
            )

    def on_remove_shots(self, confirm=True):
        # Get the selection model from the treeview
        selection_model = self.ui.shot_treeview.selectionModel()
        # Create a list of select row indices
        selected_row_list = [index.row() for index in selection_model.selectedRows()]
        # sort in descending order to prevent index changes of rows to be deleted
        selected_row_list.sort(reverse=True)

        if confirm:
            if not self.question_dialog(f'Remove {len(selected_row_list)} shots?'):
                return

        for row in selected_row_list:
            item = self.shot_model.item(row, SHOT_MODEL__CHECKBOX_INDEX)
            shutter_item = self.shot_model.item(row, SHOT_MODEL__SHUTTER_INDEX)
            shot = item.data()
            # unselect shot
            item.setCheckState(QtCore.Qt.Unchecked)
            shutter_item.setCheckState(QtCore.Qt.Unchecked)
            # remove shot from markers list
            shot_combobox_index = self.ui.markers_comboBox.findText(os.path.basename(shot.path))
            self.ui.markers_comboBox.removeItem(shot_combobox_index)
            # remove row
            self.shot_model.removeRow(row)

    def on_shot_selection_changed(self, item):
        if self.shot_model.indexFromItem(item).column() == SHOT_MODEL__CHECKBOX_INDEX:

            # add or remove a colour for this shot
            checked = item.checkState()
            row = self.shot_model.indexFromItem(item).row()
            colour_item = self.shot_model.item(row, SHOT_MODEL__COLOUR_INDEX)
            check_shutter = self.shot_model.item(row, SHOT_MODEL__SHUTTER_INDEX)

            if checked:
                colour = colour_item.data(QtCore.Qt.UserRole)
                if colour is not None:
                    colour = colour()
                else:
                    colour = self.shot_colour_delegate.get_next_colour()

                colour_item.setEditable(True)
                pixmap = QtGui.QPixmap(20, 20)
                pixmap.fill(colour)
                icon = QtGui.QIcon(pixmap)
                colour_item.setData(lambda clist=self.shot_colour_delegate._colours, colour=colour: int_to_enum(clist, colour), QtCore.Qt.UserRole)
                colour_item.setData(icon, QtCore.Qt.DecorationRole)
                shot_combobox_index = self.ui.markers_comboBox.findText(os.path.basename(item.data().path))
                self.ui.markers_comboBox.model().item(shot_combobox_index).setEnabled(True)
                if self.ui.markers_comboBox.currentIndex() == 0:
                    self.ui.markers_comboBox.setCurrentIndex(shot_combobox_index)
                if item.data().shutter_times != {}:
                    check_shutter.setEnabled(True)
                else:
                    check_shutter.setEnabled(False)
                    check_shutter.setToolTip("This shot doesn't contain shutter markers")
            else:
                shot_combobox_index = self.ui.markers_comboBox.findText(os.path.basename(item.data().path))
                self.ui.markers_comboBox.model().item(shot_combobox_index).setEnabled(False)
                if shot_combobox_index == self.ui.markers_comboBox.currentIndex():
                    self.ui.markers_comboBox.setCurrentIndex(0)
                colour_item.setEditable(False)
                check_shutter.setEnabled(False)

            self.update_channels_treeview()
        elif self.shot_model.indexFromItem(item).column() == SHOT_MODEL__COLOUR_INDEX:
            # update the plot colours

            # get reference to the changed shot
            current_shot = self.shot_model.item(self.shot_model.indexFromItem(item).row(), SHOT_MODEL__CHECKBOX_INDEX).data()

            # find and update the pen of the plot items
            for channel in self.plot_items.keys():
                for shot in self.plot_items[channel]:
                    if shot == current_shot:
                        colour = item.data(QtCore.Qt.UserRole)
                        self.plot_items[channel][shot].setPen(pg.mkPen(QtGui.QColor(colour()), width=2))
        elif self.shot_model.indexFromItem(item).column() == SHOT_MODEL__SHUTTER_INDEX:
            current_shot = self.shot_model.item(self.shot_model.indexFromItem(item).row(), SHOT_MODEL__CHECKBOX_INDEX).data()
            self.on_toggle_shutter(item.checkState(), current_shot)

    def load_shot(self, filepath):
        logger.info(f'loading run from {filepath:s}')
        shot = Shot(filepath)

        # add shot to shot list
        # Create Items
        items = []
        colour_item = QtGui.QStandardItem('')
        colour_item.setEditable(False)
        colour_item.setToolTip('Double-click to change colour')
        items.append(colour_item)

        check_shutter = QtGui.QStandardItem()
        check_shutter.setCheckable(True)
        check_shutter.setCheckState(QtCore.Qt.Unchecked)  # options are Qt.Checked OR Qt.Unchecked
        check_shutter.setEnabled(False)
        check_shutter.setToolTip("Toggle shutter markers")
        items.append(check_shutter)

        check_item = QtGui.QStandardItem(shot.path)
        check_item.setEditable(False)
        check_item.setCheckable(True)
        check_item.setCheckState(QtCore.Qt.Unchecked)  # options are Qt.Checked OR Qt.Unchecked
        check_item.setData(shot)
        check_item.setToolTip(filepath)
        items.append(check_item)
        self.shot_model.appendRow(items)
        self.ui.markers_comboBox.addItem(os.path.basename(shot.path), shot)
        shot_combobox_index = self.ui.markers_comboBox.findText(os.path.basename(shot.path))
        self.ui.markers_comboBox.model().item(shot_combobox_index).setEnabled(False)

    def get_selected_shots_and_colours(self):
        # get the ticked shots
        ticked_shots = {}
        for i in range(self.shot_model.rowCount()):
            item = self.shot_model.item(i, SHOT_MODEL__CHECKBOX_INDEX)
            colour_item = self.shot_model.item(i, SHOT_MODEL__COLOUR_INDEX)
            shutter_item = self.shot_model.item(i, SHOT_MODEL__SHUTTER_INDEX)
            if item.checkState() == QtCore.Qt.Checked:
                shot = item.data()
                colour_item_data = colour_item.data(QtCore.Qt.UserRole)
                ticked_shots[shot] = (colour_item_data(), shutter_item.checkState())
        return ticked_shots

    def update_channels_treeview(self):
        ticked_shots = self.get_selected_shots_and_colours()

        # get set of channels
        channels = {}
        for shot in ticked_shots.keys():
            channels[shot] = set(shot.channels)
        channels_set = frozenset().union(*channels.values())

        # now find channels in channels_set which are not in the treeview, and add them
        # now find channels in channels set which are already in the treeview, but deactivated, and activate them
        treeview_channels_dict = {}
        deactivated_treeview_channels_dict = {}
        for i in range(self.channel_model.rowCount()):
            item = self.channel_model.item(i, CHANNEL_MODEL__CHECKBOX_INDEX)
            # Sanity check
            if str(item.text()) in treeview_channels_dict:
                raise RuntimeError("A duplicate channel name was detected in the treeview due to an internal error. Please lodge a bugreport detailing how the channels with the same name appeared in the channel treeview. Please restart the application")

            treeview_channels_dict[str(item.text())] = i
            if not item.isEnabled():
                deactivated_treeview_channels_dict[str(item.text())] = i
        treeview_channels = set(treeview_channels_dict.keys())
        deactivated_treeview_channels = set(deactivated_treeview_channels_dict.keys())

        # speed up working with self.channel_model by blocking signals and later reenabeling them
        self.channel_model.blockSignals(True)

        # find list of channels to work with
        channels_to_add = channels_set.difference(treeview_channels)
        for channel in sorted(channels_to_add):
            items = []
            check_item = QtGui.QStandardItem(channel)
            check_item.setEditable(False)
            check_item.setCheckable(True)
            check_item.setCheckState(QtCore.Qt.Unchecked)
            items.append(check_item)
            self.channel_model.appendRow(items)

        channels_to_reactivate = deactivated_treeview_channels.intersection(channels_set)
        for channel in channels_to_reactivate:
            for i in range(self.channel_model.columnCount()):
                item = self.channel_model.item(deactivated_treeview_channels_dict[channel], i)
                item.setEnabled(True)
                item.setSelectable(True)

        # now find channels in the treeview which are not in the channels_set and deactivate them
        channels_to_deactivate = treeview_channels.difference(channels_set)
        for channel in channels_to_deactivate:
            for i in range(self.channel_model.columnCount()):
                item = self.channel_model.item(treeview_channels_dict[channel], i)
                item.setEnabled(False)
                item.setSelectable(False)

        self.channel_model.blockSignals(False)
        self.channel_model.layoutChanged.emit()

        self.update_plots()

    def update_plots(self):
        # get list of selected shots
        ticked_shots = self.get_selected_shots_and_colours()

        # find stop time of longest ticked shot

        largest_stop_time = 0
        stop_time_set = False
        for shot in ticked_shots.keys():
            if self.scale_time:
                st = self.scalehandler.get_scaled_time(shot.stop_time)
            else:
                st = shot.stop_time
            if st > largest_stop_time:
                largest_stop_time = st
                stop_time_set = True
        if not stop_time_set:
            largest_stop_time = 1.0

        # Update the range of the link plot
        self._hidden_plot[1].setData([0, largest_stop_time], [0, 1e-9])

        # Update plots
        for i in range(self.channel_model.rowCount()):
            check_item = self.channel_model.item(i, CHANNEL_MODEL__CHECKBOX_INDEX)
            channel = str(check_item.text())
            if check_item.checkState() == QtCore.Qt.Checked and check_item.isEnabled():
                # we want to show this plot
                # does a plot already exist? If yes, show it
                if channel in self.plot_widgets:
                    self.plot_widgets[channel].show()
                    # update the plot
                    # are there are plot items for this channel which are shown that should not be?
                    to_delete = []
                    for shot in self.plot_items[channel]:
                        if shot not in ticked_shots.keys():
                            self.plot_widgets[channel].removeItem(self.plot_items[channel][shot])
                            # Remove Shutter Markers of unticked Shots
                            if shot in self.shutter_lines[channel]:
                                for line in self.shutter_lines[channel][shot][0]:
                                    self.plot_widgets[channel].removeItem(line)
                                for line in self.shutter_lines[channel][shot][1]:
                                    self.plot_widgets[channel].removeItem(line)
                                self.shutter_lines[channel].pop(shot)
                            to_delete.append(shot)
                    for shot in to_delete:
                        del self.plot_items[channel][shot]

                    # do we need to add any plot items for shots that were not previously selected?
                    for shot, (colour, shutters_checked) in ticked_shots.items():
                        if shot not in self.plot_items[channel]:
                            # Add empty plot as it the custom resampling we do will happen quicker if we don't attempt to first plot all of the data
                            plot_item = self.plot_widgets[channel].plot([0, 0], [0], pen=pg.mkPen(QtGui.QColor(colour), width=2), stepMode='center')
                            self.plot_items[channel][shot] = plot_item

                        # Add Shutter Markers of newly ticked Shots
                        self.add_shutter_markers(shot, channel, shutters_checked)

                    for t, m in self.all_markers.items():
                        color = m['color']
                        color = QtGui.QColor(color[0], color[1], color[2])
                        if self.scale_time and self.scalehandler is not None:
                            t = self.scalehandler.get_scaled_time(t)
                        line = self.plot_widgets[channel].addLine(x=t, pen=pg.mkPen(color=color, width=1.5, style=QtCore.Qt.DashLine))
                        self.all_marker_items[line] = self.plot_widgets[channel]

                # If no, create one
                else:
                    self.create_plot(channel, ticked_shots)

            else:
                if channel not in self.plot_widgets:
                    self.create_plot(channel, ticked_shots)
                self.plot_widgets[channel].hide()

        self._resample = True

    def create_plot(self, channel, ticked_shots):
        self.plot_widgets[channel] = pg.PlotWidget()  # name=channel)
        self.plot_widgets[channel].setMinimumHeight(200)
        self.plot_widgets[channel].setMaximumHeight(200)
        self.plot_widgets[channel].setLabel('bottom', 'Time', units='s')
        self.plot_widgets[channel].showAxis('right', True)
        self.plot_widgets[channel].showAxis('bottom', True)
        self.plot_widgets[channel].setXLink('runviewer - time axis link')
        self.plot_widgets[channel].sigXRangeChanged.connect(self.on_x_range_changed)
        self.plot_widgets[channel].scene().sigMouseMoved.connect(lambda pos: self.mouseMovedEvent(pos, self.plot_widgets[channel], channel))
        self.ui.plot_layout.insertWidget(self.ui.plot_layout.count() - 1, self.plot_widgets[channel])
        self.shutter_lines[channel] = {}  # initialize Storage for shutter lines
        self.plot_items.setdefault(channel, {})

        has_units = False
        units = ''
        for shot, (colour, shutters_checked) in ticked_shots.items():
            if channel in shot.traces:
                # Add empty plot as it the custom resampling we do will happen quicker if we don't attempt to first plot all of the data
                plot_item = self.plot_widgets[channel].plot([0, 0], [0], pen=pg.mkPen(QtGui.QColor(colour), width=2), stepMode='center')
                self.plot_items[channel][shot] = plot_item

                if len(shot.traces[channel]) == 3:
                    has_units = True
                    units = shot.traces[channel][2]

                # Add Shutter Markers of ticked Shots
                self.add_shutter_markers(shot, channel, shutters_checked)

        if has_units:
            self.plot_widgets[channel].setLabel('left', channel, units=units)
        else:
            self.plot_widgets[channel].setLabel('left', channel)

    def add_shutter_markers(self, shot, channel, shutters_checked):
        if shot not in self.shutter_lines[channel] and channel in shot.shutter_times:
            self.shutter_lines[channel][shot] = [[], []]

            open_color = QtGui.QColor(0, 255, 0)
            close_color = QtGui.QColor(255, 0, 0)

            for t, val in shot.shutter_times[channel].items():
                scaled_t = t
                if val:  # val != 0, shutter open
                    line = self.plot_widgets[channel].addLine(x=scaled_t, pen=pg.mkPen(color=open_color, width=4., style=QtCore.Qt.DotLine))
                    self.shutter_lines[channel][shot][1].append(line)
                    if not shutters_checked:
                        line.hide()
                else:  # else shutter close
                    line = self.plot_widgets[channel].addLine(x=scaled_t, pen=pg.mkPen(color=close_color, width=4., style=QtCore.Qt.DotLine))
                    self.shutter_lines[channel][shot][0].append(line)
                    if not shutters_checked:
                        line.hide()

    def on_x_range_changed(self, *args):
        self._resample = True

    @inmain_decorator(wait_for_return=True)
    def _get_resample_params(self, channel, shot):
        rect = self.plot_items[channel][shot].getViewBox().viewRect()
        xmin, xmax = rect.left(), rect.width() + rect.left()
        dx = xmax - xmin
        view_range = self.plot_widgets[channel].viewRange()
        return view_range[0][0], view_range[0][1], dx

    def resample(self, data_x, data_y, xmin, xmax, stop_time, num_pixels):
        """Downsample a trace for plotting, keeping short spikes visible."""
        x_out = numpy.float64(numpy.linspace(xmin, xmax, 3 * 2000 + 2))
        y_out = numpy.empty(len(x_out) - 1, dtype=numpy.float64)
        data_x = numpy.float64(data_x)
        data_y = numpy.float64(data_y)

        _resample(data_x, data_y, x_out, y_out, numpy.float64(stop_time))
        return x_out, y_out

    def _resample_thread(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count()) as executer:
            while True:
                if self._resample:
                    self._resample = False
                    channel_data = self.__get_all_resample_params()

                    results = []
                    for args in channel_data:
                        results.append(executer.submit(self.__pool_resample, *args))

                    # wait for all inmain_later calls from threadpool to finish before we trigger a new resample
                    for future in results:
                        result = future.result()
                        if isinstance(result, Queue):
                            result.get()
                            
                time.sleep(0.1)

    @inmain_decorator(wait_for_return=True)
    def __get_all_resample_params(self):
        # The plot item is taken here, on the main thread, which removes it when a
        # shot is unticked:
        return [(channel, shot, colour, self.plot_items[channel][shot],
                 *self._get_resample_params(channel, shot))
            for shot, (colour, shutters_checked) in self.get_selected_shots_and_colours().items()
                for channel in shot.traces
                    if self.channel_checked_and_enabled(channel)
                    and shot in self.plot_items.get(channel, {})
        ]

    def __pool_resample(self, channel, shot, colour, plot_item, xmin, xmax, dx):
        try:
            if self.scale_time:
                xnew, ynew = self.resample(shot.scaled_times(channel), shot.traces[channel][1], xmin, xmax, shot.stop_time, dx)
            else:
                xnew, ynew = self.resample(shot.traces[channel][0], shot.traces[channel][1], xmin, xmax, shot.stop_time, dx)
            return inmain_later(plot_item.setData, xnew, ynew, pen=pg.mkPen(QtGui.QColor(colour), width=2), stepMode='center')
        except Exception:
            logger.exception(f'Could not resample {channel}')

    @inmain_decorator(wait_for_return=True)
    def channel_checked_and_enabled(self, channel):
        index = self.channel_model.index(0, CHANNEL_MODEL__CHANNEL_INDEX)
        indexes = self.channel_model.match(index, QtCore.Qt.DisplayRole, channel, 1, QtCore.Qt.MatchExactly)
        if len(indexes) == 1:
            check_item = self.channel_model.itemFromIndex(indexes[0])
            if check_item.checkState() == QtCore.Qt.Checked and check_item.isEnabled():
                return True
        return False

    def on_x_axis_reset(self):
        ticked_shots = self.get_selected_shots_and_colours()
        largest_stop_time = 0
        stop_time_set = False
        for shot in ticked_shots.keys():
            if self.scale_time:
                st = self.scalehandler.get_scaled_time(shot.stop_time)
            else:
                st = shot.stop_time
            if st > largest_stop_time:
                largest_stop_time = st
                stop_time_set = True
        if not stop_time_set:
            largest_stop_time = 1.0

        # Update the range of the link plot
        self._hidden_plot[1].setData([0, largest_stop_time], [0, 1e-9])

        self._hidden_plot[0].enableAutoRange(axis=pg.ViewBox.XAxis)

    def on_y_axes_reset(self):
        for plot_widget in self.plot_widgets.values():
            plot_widget.enableAutoRange(axis=pg.ViewBox.YAxis)

    def _enable_selected_shots(self):
        self.update_ticks_of_selected_shots(QtCore.Qt.Checked)

    def _disable_selected_shots(self):
        self.update_ticks_of_selected_shots(QtCore.Qt.Unchecked)

    def update_ticks_of_selected_shots(self, state):
        # Get the selection model from the treeview
        selection_model = self.ui.shot_treeview.selectionModel()
        # Create a list of select row indices
        selected_row_list = [index.row() for index in sorted(selection_model.selectedRows())]
        # for each row selected
        for row in selected_row_list:
            check_item = self.shot_model.item(row, SHOT_MODEL__CHECKBOX_INDEX)
            check_item.setCheckState(state)

    def update_plot_positions(self):
        # addWidget moves a widget already in the layout to the end:
        for i in range(self.channel_model.rowCount()):
            check_item = self.channel_model.item(i, CHANNEL_MODEL__CHECKBOX_INDEX)
            channel = str(check_item.text())
            if channel in self.plot_widgets:
                self.ui.plot_layout.addWidget(self.plot_widgets[channel])
                if check_item.checkState() == QtCore.Qt.Checked and check_item.isEnabled():
                    self.plot_widgets[channel].show()
                else:
                    self.plot_widgets[channel].hide()
        self.ui.plot_layout.addWidget(self._time_axis_plot[0])


class Shot:
    def __init__(self, path):
        self.path = path

        # Store list of traces
        self._traces = None
        # store list of channels
        self._channels = None
        # store list of markers
        self._markers = None
        self.cached_scaler = None
        self._scalehandler = None
        self._scaled_x = {}

        # store list of shutter changes and callibrations
        self._shutter_times = None
        self._shutter_calibrations = {}

        # Load connection table
        self.connection_table = ConnectionTable(path)

        # open h5 file
        with h5py.File(path, 'r') as file:
            # Get master pseudoclock
            self.master_pseudoclock_name = ensure_str(
                file['connection table'].attrs['master_pseudoclock']
            )

            # get stop time
            self.stop_time = file['devices'][self.master_pseudoclock_name].attrs['stop_time']

            self.device_names = list(file['devices'].keys())

            # Get Shutter Calibrations
            if 'calibrations' in file and 'Shutter' in file['calibrations']:
                for name, open_delay, close_delay in numpy.array(file['calibrations']['Shutter']):
                    name = ensure_str(name)
                    self._shutter_calibrations[name] = [open_delay, close_delay]

    def _load(self):
        if self._channels is None:
            self._channels = {}
        if self._traces is None:
            self._traces = {}
        if self._markers is None:
            self._markers = {}
        if self._shutter_times is None:
            self._shutter_times = {}

        self._load_markers()
        # Let's walk the connection table, starting with the master pseudoclock
        master_pseudoclock_device = self.connection_table.find_by_name(self.master_pseudoclock_name)

        self._load_device(master_pseudoclock_device)

    def _load_markers(self):
        with h5py.File(self.path, 'r') as file:
            if "time_markers" in file:
                for row in file["time_markers"]:
                    self._markers[row['time']] = {'color': row['color'].tolist()[0], 'label': row['label']}
            if 0 not in self._markers:
                self._markers[0] = {'color': [0,0,0], 'label': 'Start'}
            if self.stop_time not in self._markers:
                self._markers[self.stop_time] = {'color': [0,0,0], 'label' : 'End'}

    def add_trace(self, name, trace, parent_device_name, connection):
        name = str(name)
        self._channels[name] = {'device_name': parent_device_name, 'port': connection}
        self._traces[name] = trace

        # add shutter times
        con = self.connection_table.find_by_name(name)
        if con.device_class == "Shutter" and 'open_state' in con.properties:
            self.add_shutter_times([(name, con.properties['open_state'])])

    # Temporary solution to physical shutter times
    def add_shutter_times(self, shutters):
        for name, open_state in shutters:
            x_values, y_values = self._traces[name]
            if len(x_values) > 0:
                change_indices = numpy.where(y_values[:-1] != y_values[1:])[0]
                change_indices += 1 # use the index of the value that is changed to
                change_values = list(zip(x_values[change_indices], y_values[change_indices]))
                change_values.insert(0, (x_values[0], y_values[0])) # insert first value
                self._shutter_times[name] = {x_value + (self._shutter_calibrations[name][0] if y_value == open_state else self._shutter_calibrations[name][1]): 1 if y_value == open_state else 0 for x_value, y_value in change_values}

    def _load_device(self, device, clock=None):
        try:
            logger.info(f'loading {device.name}')
            module = device.device_class
            # Load the master pseudoclock class
            device_class = device_registry.get_runviewer_parser(module)
            device_instance = device_class(self.path, device)
            clocklines_and_triggers = device_instance.get_traces(self.add_trace, clock)

            for name, trace in clocklines_and_triggers.items():
                child_device = self.connection_table.find_by_name(name)
                for grandchild_device_name, grandchild_device in child_device.child_list.items():
                    self._load_device(grandchild_device, trace)

        except Exception as e:

            if hasattr(device, 'name'):
                logger.info(f'Failed to load device {device.name:s}, exception was:\n'+
                            ''.join(traceback.format_exception(type(e), e, e.__traceback__)))
            else:
                logger.info('Failed to load device (unknown name, device object does not have attribute name), exception was:\n'+
                            ''.join(traceback.format_exception(type(e), e, e.__traceback__)))

    def scaled_times(self, channel):
        if self.cached_scaler != app.scalehandler:
            self.cached_scaler = app.scalehandler
            self._scaled_x = {}
        if channel not in self._scaled_x:
            self._scaled_x[channel] = self.cached_scaler.get_scaled_time(self._traces[channel][0])

        return self._scaled_x[channel]

    @property
    def channels(self):
        if self._channels is None:
            self._load()

        return self._channels.keys()

    @property
    def markers(self):
        if self._markers is None:
            self._load()
        return self._markers

    @property
    def traces(self):
        if self._traces is None:
            self._load()
        return self._traces

    @property
    def shutter_times(self):
        if self._shutter_times is None:
            self._load()
        return self._shutter_times



class RunviewerServer(ZMQServer):
    def __init__(self, port, shots_queue, **kwargs):
        self.shots_queue = shots_queue
        super().__init__(port, **kwargs)

    def handle_add_shot(self, filepath):
        logger.info(f'Received shot file: {filepath}')
        # we add the shot to a queue so that we don't have to wait for the app to come up before
        # responding to runmanager
        self.shots_queue.put(labscript_utils.shared_drive.path_to_local(filepath))


if __name__ == "__main__":
    qapplication = splash.qapplication

    shots_to_process_queue = Queue()

    exp_config = LabConfig(required_params = {"default": ["apparatus_name"], "paths": ["shared_drive", "experiment_shot_storage"], 'ports': ['runviewer']})

    port = int(exp_config.get('ports', 'runviewer'))
    # Start experiment server
    runviewer_server = RunviewerServer(port, shots_to_process_queue)

    app = RunViewer(exp_config)
    splash.hide()

    sys.exit(exec_qapplication(qapplication))
