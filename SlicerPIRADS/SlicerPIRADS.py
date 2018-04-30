import slicer
import os
import qt
import vtk
import ctk
import logging
import string
from slicer.ScriptedLoadableModule import *
from collections import OrderedDict

from qSlicerMultiVolumeExplorerModuleWidget import qSlicerMultiVolumeExplorerSimplifiedModuleWidget
from qSlicerMultiVolumeExplorerModuleHelper import qSlicerMultiVolumeExplorerModuleHelper as MVHelper

from SlicerDevelopmentToolboxUtils.mixins import UICreationHelpers, GeneralModuleMixin, ModuleWidgetMixin
from SlicerDevelopmentToolboxUtils.icons import Icons
from SlicerDevelopmentToolboxUtils.buttons import ModuleSettingsButton, CrosshairButton
from SlicerDevelopmentToolboxUtils.helpers import WatchBoxAttribute
from SlicerDevelopmentToolboxUtils.widgets import DICOMBasedInformationWatchBox
from SlicerDevelopmentToolboxUtils.constants import DICOMTAGS

from SlicerPIRADSLogic.Configuration import SlicerPIRADSConfiguration
from SlicerPIRADSLogic.HangingProtocol import HangingProtocolFactory
from SlicerPIRADSWidgets.StudyAssessmentWidget import StudyAssessmentWidget
from SlicerPIRADSWidgets.DataSelectionDialog import DataSelectionDialog
from SlicerPIRADSWidgets.FindingsWidget import FindingsWidget

from SlicerLayoutButtons import SlicerLayoutButtonsWidget


class SlicerPIRADS(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Slicer PIRADS"
    self.parent.categories = ["Informatics", "Quantification", "Segmentation"]
    self.parent.dependencies = ["SlicerDevelopmentToolbox"]
    self.parent.contributors = ["Christian Herz (SPL, BWH)", "Andrey Fedorov (SPL, BWH)"]
    self.parent.helpText = """
      
    """
    self.parent.acknowledgementText = """ 
      Surgical Planning Laboratory, Brigham and Women's Hospital, Harvard 
      Medical School, Boston, USA This work was supported in part by the 
      National Institutes of Health through grants U24 CA180918,
      R01 CA111288 and P41 EB015898.
    """


class SlicerPIRADSWidget(ScriptedLoadableModuleWidget, GeneralModuleMixin):

  @property
  def loadedVolumeNodes(self):
    return self._loadedVolumeNodes

  @loadedVolumeNodes.setter
  def loadedVolumeNodes(self, volumes):
    self._loadedVolumeNodes = OrderedDict({volume.GetID: volume for volume in volumes})
    self.updateGUIFromData()

  def __init__(self, parent=None):
    ScriptedLoadableModuleWidget.__init__(self, parent)
    self.modulePath = os.path.dirname(slicer.util.modulePath(self.moduleName))
    SlicerPIRADSConfiguration(self.moduleName, os.path.join(self.modulePath, 'Resources', "default.cfg"))
    self._loadedVolumeNodes = OrderedDict()
    self.logic = SlicerPIRADSModuleLogic()

  def updateGUIFromData(self):
    try:
      instanceUID = self._loadedVolumeNodes.values()[0].GetAttribute("DICOM.instanceUIDs").split(" ")[0]
      filename = slicer.dicomDatabase.fileForInstance(instanceUID)
      self._patientWatchBox.sourceFile = filename
    except:
      self._patientWatchBox.sourceFile = None
    return
    self._studyAssessmentWidget.enabled = len(self._loadedVolumeNodes) > 0
    self._findingsWidget.enabled = len(self._loadedVolumeNodes) > 0

  def setup(self):
    # TODO: following line is only for the purpose of testing
    self._loadedVolumeNodes = OrderedDict({volume.GetID: volume for volume
                                           in slicer.util.getNodesByClass('vtkMRMLScalarVolumeNode')})
    ScriptedLoadableModuleWidget.setup(self)
    self._setupPatientWatchBox()
    self._setupViewSettingGroupBox()
    self._setupCollapsibleLayoutButton()
    self._setupCollapsibleMultiVolumeExplorerButton()
    self._studyAssessmentWidget = StudyAssessmentWidget()
    self._findingsWidget = FindingsWidget(maximumNumber=4)
    self.layout.addWidget(self._collapsibleLayoutButton)
    # self.layout.addWidget(self._collapsibleMultiVolumeButton)
    self.layout.addWidget(self._studyAssessmentWidget)
    self.layout.addWidget(self._findingsWidget)
    self._stepButtonGroup = qt.QButtonGroup()
    self._stepButtonGroup.addButton(self._studyAssessmentWidget, 1)
    self._stepButtonGroup.addButton(self._findingsWidget, 3)
    self.layout.addStretch(1)
    self._setupConnections()
    self.updateGUIFromData()

  def _setupPatientWatchBox(self):
    WatchBoxAttribute.TRUNCATE_LENGTH = 20
    patientWatchBoxInformation = [WatchBoxAttribute('PatientName', "Patient's Name: ", DICOMTAGS.PATIENT_NAME),
                                  WatchBoxAttribute('PatientID', 'Patient ID: ', DICOMTAGS.PATIENT_ID),
                                  WatchBoxAttribute('DOB', "Patient's Birth Date: ", DICOMTAGS.PATIENT_BIRTH_DATE),
                                  WatchBoxAttribute('StudyDate', 'Study Date: ', DICOMTAGS.STUDY_DATE)]
    self._patientWatchBox = DICOMBasedInformationWatchBox(patientWatchBoxInformation, title="Patient Information",
                                                         columns=2)
    self.layout.addWidget(self._patientWatchBox)

  def _setupViewSettingGroupBox(self):
    self._loadDataButton = UICreationHelpers.createButton("", toolTip="Load Data")
    self._loadDataButton.setIcon(Icons.open)
    self._crosshairButton = CrosshairButton()
    self._settingsButton = ModuleSettingsButton(self.moduleName)
    self._settingsButton.enabled = False
    self.layout.addWidget(UICreationHelpers.createHLayout([self._loadDataButton, self._crosshairButton,
                                                           self._settingsButton]))

  def _setupCollapsibleLayoutButton(self):
    self._collapsibleLayoutButton = ctk.ctkCollapsibleButton()
    self._collapsibleLayoutButton.text = "Layout"
    self._collapsibleLayoutButton.collapsed = 0
    self._collapsibleLayoutButton.setLayout(qt.QVBoxLayout())
    self._layoutButtonsWidget = SlicerLayoutButtonsWidget(parent=self._collapsibleLayoutButton)
    self._layoutButtonsWidget.setup()
    self._layoutButtonsWidget.hideReloadAndTestArea()
    self._layoutButtonsWidget.setDisplayForegroundOnly()

  def _setupCollapsibleMultiVolumeExplorerButton(self):
    self._collapsibleMultiVolumeButton = ctk.ctkCollapsibleButton()
    self._collapsibleMultiVolumeButton.text = "MultiVolumeExplorer"
    self._collapsibleMultiVolumeButton.collapsed = True
    self._collapsibleMultiVolumeButton.setLayout(qt.QFormLayout())
    self._multiVolumeExplorer = SlicerPIRADSMultiVolumeExplorer(self._collapsibleMultiVolumeButton.layout())
    self._multiVolumeExplorer.setup()

  def _setupConnections(self):
    self._loadDataButton.clicked.connect(self._onLoadButtonClicked)
    # self._multiVolumeExplorer.frameSlider.connect('valueChanged(double)', self.onSliderChanged)

  # def onSliderChanged(self, newValue):
  #   newValue = int(newValue)
  #   seriesNumber = self._multiVolumeExplorer.getCurrentSeriesNumber()
  #   if seriesNumber in self.seriesMap.keys():
  #     multiVolumeNode = self.seriesMap[seriesNumber]['MultiVolume']
  #     scalarVolumeNode = MVHelper.extractFrame(self.seriesMap[seriesNumber]['Volume'],
  #                                                              multiVolumeNode,
  #                                                              newValue)
  #     scalarVolumeNode.SetName(multiVolumeNode.GetName().split('_multivolume')[0])
  #     self.seriesMap[seriesNumber]['Volume'] = scalarVolumeNode
  #     self.seriesMap[seriesNumber]['FrameNumber'] = newValue
  #     multiVolumeNode.GetDisplayNode().SetFrameComponent(newValue)

  def _onLoadButtonClicked(self):
    self._dataSelectionDialog = DataSelectionDialog()
    self._loadedVolumeNodes = OrderedDict()

    nodeAddedObserver = slicer.mrmlScene.AddObserver(slicer.mrmlScene.NodeAddedEvent, self._onVolumeNodeAdded)
    nodeRemovedObserver = slicer.mrmlScene.AddObserver(slicer.mrmlScene.NodeRemovedEvent, self._onVolumeNodeRemoved)
    try:
      if self._dataSelectionDialog.exec_():
        self._hangingProtocol = HangingProtocolFactory.getHangingProtocol(self.loadedVolumeNodes.values())
        if not self._hangingProtocol:
          raise RuntimeError("No eligible hanging protocol found.")
        background = self._loadedVolumeNodes.values()[0]
        self.logic.viewerPerVolume(volumeNodes=self._loadedVolumeNodes.values(), layout=self._hangingProtocol.LAYOUT,
                                   background=background)
        ModuleWidgetMixin.linkAllSliceWidgets(1)
        sliceWidgets = list(ModuleWidgetMixin.getAllVisibleWidgets())
        if sliceWidgets:
          sliceWidget = sliceWidgets[0].mrmlSliceNode().RotateToVolumePlane(background)
        # self.checkForMultiVolumes()
    except Exception as exc:
      logging.error(exc.message)
    finally:
      slicer.mrmlScene.RemoveObserver(nodeAddedObserver)
      slicer.mrmlScene.RemoveObserver(nodeRemovedObserver)
      self.updateGUIFromData()

  def checkForMultiVolumes(self):
    multiVolumes = slicer.util.getNodesByClass('vtkMRMLMultiVolumeNode')
    self._multiVolumeExplorer.showInputMultiVolumeSelector(len(multiVolumes) > 1)
    multiVolume = None
    if len(multiVolumes) == 1:
      multiVolume = multiVolumes[0]
    elif len(multiVolumes) > 1:
      multiVolume = max(multiVolumes, key=lambda mv: mv.GetNumberOfFrames)
      # TODO: set selector
    self._multiVolumeExplorer.setMultiVolume(multiVolume)
    self.showMultiVolumeExplorer(len(multiVolumes) > 0)

  def showMultiVolumeExplorer(self, show):
    if show:
      self._collapsibleMultiVolumeButton.show()
    else:
      self._collapsibleMultiVolumeButton.hide()

  @vtk.calldata_type(vtk.VTK_OBJECT)
  def _onVolumeNodeAdded(self, caller, event, callData):
    if isinstance(callData, slicer.vtkMRMLScalarVolumeNode):
      self._loadedVolumeNodes[callData.GetID()] = callData

  @vtk.calldata_type(vtk.VTK_OBJECT)
  def _onVolumeNodeRemoved(self, caller, event, callData):
    if isinstance(callData, slicer.vtkMRMLScalarVolumeNode):
      try:
        del self._loadedVolumeNodes[callData.GetID()]
      except KeyError:
        pass


class SlicerPIRADSModuleLogic(ScriptedLoadableModuleLogic):

  def __init__(self):
    ScriptedLoadableModuleLogic.__init__(self)

  @staticmethod
  def viewerPerVolume(volumeNodes,layout,background,orientation='Axial',opacity=1.0):
    """ Load each volume in the scene into its own slice viewer and link them all together.
    If background is specified, put it in the background of all viewers and make the other volumes be the foreground.
    If label is specified, make it active as the label layer of all viewers. Return a map of slice nodes indexed by
    the view name (given or generated). Opacity applies only when background is selected.
    """

    if not volumeNodes:
      raise ValueError("VolumeNodes are supposed to be non empty")

    layoutManager = slicer.app.layoutManager()
    layoutManager.setLayout(layout)

    sliceWidgets = list(ModuleWidgetMixin.getAllVisibleWidgets())

    slicer.app.processEvents()

    for index, volume in enumerate(volumeNodes):
      sliceWidget = sliceWidgets[index]
      volumeNodeID = volume.GetID()

      compositeNode = sliceWidget.mrmlSliceCompositeNode()
      compositeNode.SetBackgroundVolumeID(background.GetID())
      compositeNode.SetForegroundVolumeID(volumeNodeID)
      compositeNode.SetForegroundOpacity(opacity)

      sliceNode = sliceWidget.mrmlSliceNode()
      sliceNode.SetOrientation(orientation)
      sliceNode.RotateToVolumePlane(volume)
      sliceWidget.fitSliceToBackground()


class SlicerPIRADSMultiVolumeExplorer(qSlicerMultiVolumeExplorerSimplifiedModuleWidget):

  def getCurrentSeriesNumber(self):
    ref = -1
    if self._bgMultiVolumeNode:
      name = self._bgMultiVolumeNode.GetName()
      ref = string.split(name,':')[0]
    return ref

  def showInputMultiVolumeSelector(self, show):
    if show:
      self._bgMultiVolumeSelectorLabel.show()
      self.bgMultiVolumeSelector.show()
    else:
      self._bgMultiVolumeSelectorLabel.hide()
      self.bgMultiVolumeSelector.hide()

  def setMultiVolume(self, node):
    self.bgMultiVolumeSelector.setCurrentNode(node)

  def createChart(self, sliceWidget, position):
    self._multiVolumeIntensityChart.createChart(sliceWidget, position, ignoreCurrentBackground=True)

  def refreshGUIForNewBackgroundImage(self):
    self._multiVolumeIntensityChart.reset()
    self.setFramesEnabled(True)
    self.refreshFrameSlider()
    self._multiVolumeIntensityChart.bgMultiVolumeNode = self._bgMultiVolumeNode

  def onBackgroundInputChanged(self):
    qSlicerMultiVolumeExplorerSimplifiedModuleWidget.onBackgroundInputChanged(self)
    self.popupChartButton.setEnabled(self._bgMultiVolumeNode is not None)

  def onSliderChanged(self, frameId):
    return


class SlicerPIRADSSlicelet(qt.QWidget):

  def __init__(self):
    qt.QWidget.__init__(self)
    self.mainWidget = qt.QWidget()
    self.mainWidget.objectName = "qSlicerAppMainWindow"
    self.mainWidget.setLayout(qt.QHBoxLayout())

    self.setupLayoutWidget()

    self.moduleFrame = qt.QWidget()
    self.moduleFrame.setLayout(qt.QVBoxLayout())
    self.widget = SlicerPIRADSWidget(self.moduleFrame)
    self.widget.setup()

    self.scrollArea = qt.QScrollArea()
    self.scrollArea.setWidget(self.widget.parent)
    self.scrollArea.setWidgetResizable(True)
    self.scrollArea.setMinimumWidth(self.widget.parent.minimumSizeHint.width())

    self.splitter = qt.QSplitter()
    self.splitter.setOrientation(qt.Qt.Horizontal)
    self.splitter.addWidget(self.scrollArea)
    self.splitter.addWidget(self.layoutWidget)
    self.splitter.splitterMoved.connect(self.onSplitterMoved)

    self.splitter.setStretchFactor(0, 0)
    self.splitter.setStretchFactor(1, 1)
    self.splitter.handle(1).installEventFilter(self)

    self.mainWidget.layout().addWidget(self.splitter)
    self.mainWidget.show()
    self.configureStyle()

  def configureStyle(self):
    slicer.app.setStyleSheet("""
      QWidget{
        background-color: #555555;
        color: white;
      }
    """)

  def setupLayoutWidget(self):
    # TODO: configurable ...
    self.layoutWidget = qt.QWidget()
    self.layoutWidget.setLayout(qt.QHBoxLayout())
    layoutWidget = slicer.qMRMLLayoutWidget()
    layoutManager = slicer.qSlicerLayoutManager()
    layoutManager.setMRMLScene(slicer.mrmlScene)
    layoutManager.setScriptedDisplayableManagerDirectory(slicer.app.slicerHome + "/bin/Python/mrmlDisplayableManager")
    layoutWidget.setLayoutManager(layoutManager)
    slicer.app.setLayoutManager(layoutManager)
    layoutWidget.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutFourUpView)
    self.layoutWidget.layout().addWidget(layoutWidget)

  def eventFilter(self, obj, event):
    if event.type() == qt.QEvent.MouseButtonDblClick:
      self.onSplitterClick()

  def onSplitterMoved(self, pos, index):
    vScroll = self.scrollArea.verticalScrollBar()
    vScrollbarWidth = 4 if not vScroll.isVisible() else vScroll.width + 4
    if self.scrollArea.minimumWidth != self.widget.parent.minimumSizeHint.width() + vScrollbarWidth:
      self.scrollArea.setMinimumWidth(self.widget.parent.minimumSizeHint.width() + vScrollbarWidth)

  def onSplitterClick(self):
    if self.splitter.sizes()[0] > 0:
      self.splitter.setSizes([0, self.splitter.sizes()[1]])
    else:
      minimumWidth = self.widget.parent.minimumSizeHint.width()
      self.splitter.setSizes([minimumWidth, self.splitter.sizes()[1] - minimumWidth])


if __name__ == "SlicerPIRADSSlicelet":
  slicelet = SlicerPIRADSSlicelet()