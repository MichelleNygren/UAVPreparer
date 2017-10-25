# -*- coding: utf-8 -*-
"""
/***************************************************************************
 UAVPreparer
                                 A QGIS plugin
 This plug-in examines height properties on a DSM
                              -------------------
        begin                : 2017-10-25
        git sha              : $Format:%H$
        copyright            : (C) 2017 by Aifang Chen
        email                : aifang.chen@gu.se
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from PyQt4.QtCore import QSettings, QTranslator, qVersion, QCoreApplication
from PyQt4.QtGui import QAction, QIcon, QFileDialog, QMessageBox
from qgis.gui import *
from qgis.core import QgsVectorLayer
# Initialize Qt resources from file resources.py
import resources
# Import the code for the dialog
from uav_preparer_dialog import UAVPreparerDialog
import os.path
import webbrowser
import numpy as np
import subprocess
from osgeo import gdal

class UAVPreparer:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'UAVPreparer_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)


        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&UAV Preparer')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'UAVPreparer')
        self.toolbar.setObjectName(u'UAVPreparer')

        # Declare variables
        self.outputfile = None
        self.filepath_dsm = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('UAVPreparer', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        # Create the dialog (after translation) and keep reference
        self.dlg = UAVPreparerDialog()

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/UAVPreparer/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u''),
            callback=self.run,
            parent=self.iface.mainWindow())

        # Access the raster layer
        self.layerComboManagerDSM = QgsMapLayerComboBox(self.dlg.widgetDSM)
        self.layerComboManagerDSM.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.layerComboManagerDSM.setFixedWidth(250)
        self.layerComboManagerDSM.setCurrentIndex(-1)

        # Access the vector layer and an attribute field
        self.layerComboManagerPoint = QgsMapLayerComboBox(self.dlg.widgetPointLayer)
        self.layerComboManagerPoint.setCurrentIndex(-1)
        self.layerComboManagerPoint.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.layerComboManagerPoint.setFixedWidth(250)
        self.layerComboManagerPointField = QgsFieldComboBox(self.dlg.widgetField)
        self.layerComboManagerPointField.setFilters(QgsFieldProxyModel.Numeric)
        self.layerComboManagerPoint.layerChanged.connect(self.layerComboManagerPointField.setLayer)

        # Setup of file save dialog
        self.fileDialog = QFileDialog()
        self.dlg.pushButtonSave.clicked.connect(self.savefile)

        # Setup for the Help Button
        self.dlg.helpButton.clicked.connect(self.help)

        # Setup for the Run Button
        self.dlg.runButton.clicked.connect(self.start_progress)

    def savefile(self):
        self.outputfile = self.fileDialog.getSaveFileName(None, "Save File As: ", None, "Text Files (*.txt)")
        self.dlg.textOutput.setText(self.outputfile)

    def help (self):
        url = "https://github.com/MichelleNygren/UAVPreparer"
        webbrowser.open_new_tab(url)

    def start_progress(self):

        if not self.outputfile:
            QMessageBox.critical(None, "Error", "Specify an output file")
            return

        # Acquiring geodata and attributed
        dsm_layer = self.layerComboManagerDSM.currentLayer()
        if dsm_layer is None:
            QMessageBox.critical(None, "Error", "No valid raster layer is selected")
            return
        else:
            provider = dsm_layer.dataProvider()
            filepath_dsm = str(provider.dataSourceUri())

        point_layer = self.layerComboManagerPoint.currentLayer()
        if point_layer is None:
            QMessageBox.critical(None, "Error", "No valid vector point layer is selected")
            return
        else:
            vlayer = QgsVectorLayer(point_layer.source(), "point", "ogr")

        point_field = self.layerComboManagerPointField.currentField()
        idx = vlayer.fieldNameIndex(point_field)
        if idx == -1:
            QMessageBox.critical(None, "Error", "An attribute with unique fields must be selected")
            return

        # Counts rows in vector layer
        h = vlayer.featureCount()
        newarray = np.zeros((h, 4))

        index = 0

        self.dlg.progressBar.setRange(index, h)

        for i in vlayer.getFeatures():
            self.dlg.progressBar.setValue(index+1)
            geom = i.geometry()
            pp = geom.asPoint()
            x = pp[0]
            y = pp[1]
            rSquare = 100

            square = 'gdalwarp -dstnodata -9999 -q -overwrite -te ' + \
                     str(x - rSquare) + ' ' + str(y - rSquare) + ' ' + str(x + rSquare) + ' ' + str(y + rSquare) + \
                     ' -of GTiff ' + \
                     filepath_dsm + '' + self.plugin_dir + '/clipdsm.tif'

            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.call(square, startupinfo=si)

            area = gdal.Open('C:/Users/xnygmi/Desktop/FREDRIK_GIS/London/clipdsm.tif')
            mat = np.array(area.ReadAsArray())

            max = np.max(mat)
            mean = np.mean(mat)
            min = np.min(mat)

            k = vlayer.fieldNameIndex('Id')
            newarray[index, 0] = i.attributes()[k]
            newarray[index, 1] = max
            newarray[index, 2] = mean
            newarray[index, 3] = min
            index += 1

        numformat = '%d ' +  '%6.2f ' * 3
        headertext = 'ID    Mean    Max     Min'
        np.savetxt(self.outputfile, newarray, fmt=numformat, header=headertext, delimiter=' ')

        self.iface.messageBar().pushMessage('UAV Preparer. Operation Successful!', level=QgsMessageBar.INFO, duration=5)


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&UAV Preparer'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar


    def run(self):
        """Run method that performs all the real work"""
        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            # Do something useful here - delete the line containing pass and
            # substitute with your code.
            pass
