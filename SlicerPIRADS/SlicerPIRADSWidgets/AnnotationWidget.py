import qt
import vtk
import ctk
import os
import slicer

from SegmentEditor import SegmentEditorWidget

from SlicerDevelopmentToolboxUtils.mixins import ParameterNodeObservationMixin, ModuleWidgetMixin
from SlicerDevelopmentToolboxUtils.icons import Icons


class AnnotationWidgetFactory(object):
  # TODO: write test
  # helper class for delivering widget to user with tools

  @staticmethod
  def getAnnotationWidgetForMRMLNode(mrmlNode):
    if mrmlNode.__class__.__name__ == "vtkMRMLSegmentationNode":
      return CustomSegmentEditorWidget


class AnnotationItemWidget(qt.QWidget, ParameterNodeObservationMixin):

  AnnotationToolSelectedEvent = vtk.vtkCommand.UserEvent + 301
  AnnotationToolDeselectedEvent = vtk.vtkCommand.UserEvent + 302

  ICON_MAP = {"vtkMRMLSegmentationNode": "SegmentEditor.png",
              "vtkMRMLAnnotationRulerNode": "Ruler.png",
              "vtkMRMLMarkupFiducialNode": "Fiducials.png"}

  def __init__(self, finding, seriesType):
    super(AnnotationItemWidget, self).__init__()
    self.modulePath = os.path.dirname(slicer.util.modulePath("SlicerPIRADS"))
    self._seriesType = seriesType
    self._finding = finding
    self.setup()
    self._processData()

  def setup(self):
    self.setLayout(qt.QGridLayout())
    path = os.path.join(self.modulePath, 'Resources', 'UI', 'AnnotationItemWidget.ui')
    self.ui = slicer.util.loadUI(path)
    self.visibilityButton = self.ui.findChild(qt.QPushButton, "visibilityButton")
    self.visibilityButton.setIcon(Icons.visible_on)
    self.visibilityButton.checkable = True
    self.visibilityButton.checked = True
    self._seriesTypeLabel = self.ui.findChild(qt.QLabel, "seriesTypeLabel")
    self._annotationButtonGroup = self.ui.findChild(qt.QButtonGroup, "annotationButtonGroup")
    for button in self._annotationButtonGroup.buttons():
      button.setIcon(self.getIconFromMRMLNodeClass(button.property("MRML_NODE_CLASS")))

    self.layout().addWidget(self.ui)
    self._setupConnections()
    self.enable(False)

  def _setupConnections(self):
    self._annotationButtonGroup.connect("buttonToggled(QAbstractButton*, bool)", self._onAnnotationButtonClicked)
    self.visibilityButton.toggled.connect(self._onVisibilityButtonToggled)
    self.destroyed.connect(self._cleanupConnections)

  def _onVisibilityButtonToggled(self, checked):
    self.visibilityButton.setIcon(Icons.visible_on if checked else Icons.visible_off)
    self._finding.setSeriesTypeVisible(self._seriesType, checked)

  def enable(self, enabled):
    self.enabled = enabled
    if not enabled:
      for b in self._annotationButtonGroup.buttons():
        b.checked = False

  def _onAnnotationButtonClicked(self, button, checked):
    if checked:
      for b in self._annotationButtonGroup.buttons():
        if b.checked and b is not button:
          b.checked = False
      for w in ModuleWidgetMixin.getAllVisibleWidgets():
        enabled = self._seriesType.getVolume() is \
                  slicer.mrmlScene.GetNodeByID(w.mrmlSliceCompositeNode().GetForegroundVolumeID())
        w.enabled = enabled
        w.setStyleSheet("#frame{{border: 3px ridge {};}}".format("green" if enabled else "red"))
      self.invokeEvent(self.AnnotationToolSelectedEvent, button.property("MRML_NODE_CLASS"))
    else:
      for w in ModuleWidgetMixin.getAllVisibleWidgets():
        w.enabled = True
        w.setStyleSheet("")
      self.invokeEvent(self.AnnotationToolDeselectedEvent, button.property("MRML_NODE_CLASS"))

  def _cleanupConnections(self):
    self._annotationButtonGroup.disconnect("buttonClicked(QAbstractButton*)", self._onAnnotationButtonClicked)

  def _processData(self, caller=None, event=None):
    self._seriesTypeLabel.text = self._seriesType.getName()

  @staticmethod
  def getIconFromMRMLNodeClass(name):
    modulePath = os.path.dirname(slicer.util.modulePath("SlicerPIRADS"))
    return qt.QIcon(os.path.join(modulePath, 'Resources', 'Icons', AnnotationItemWidget.ICON_MAP[name]))

  @staticmethod
  def getIconFromMRMLNode(mrmlNode):
    return AnnotationItemWidget.getIconFromMRMLNodeClass(mrmlNode.__class__.__name__)

  def getSeriesType(self):
    return self._seriesType


class AnnotationToolWidget(object):

  MRML_NODE_CLASS = None

  @property
  def annotation (self):
      return self._finding.getOrCreateAnnotation(self._seriesType, self.MRML_NODE_CLASS)

  def __init__(self, finding, seriesType):
    if not self.MRML_NODE_CLASS:
      raise NotImplementedError
    self._finding = finding
    self._seriesType = seriesType

  def _updateFromData(self):
    raise NotImplementedError

  def setData(self, finding, seriesType):
    self._finding = finding
    self._seriesType = seriesType
    self._updateFromData()

  def resetInteraction(self):
    raise NotImplementedError


class CustomSegmentEditorWidget(AnnotationToolWidget, SegmentEditorWidget):

  MRML_NODE_CLASS = "vtkMRMLSegmentationNode"

  def __init__(self, parent, finding, seriesType):
    AnnotationToolWidget.__init__(self, finding, seriesType)
    SegmentEditorWidget.__init__(self, parent)
    self.setup()

  def _updateFromData(self):
    self.editor.setSegmentationNode(self.annotation.mrmlNode)

  def setup(self):
    SegmentEditorWidget.setup(self)
    self.editor.setAutoShowMasterVolumeNode(False)
    if self.developerMode:
      self.reloadCollapsibleButton.hide()
    self.editor.switchToSegmentationsButtonVisible = False
    self.editor.segmentationNodeSelectorVisible = False
    self.editor.masterVolumeNodeSelectorVisible = False
    self.editor.setEffectButtonStyle(qt.Qt.ToolButtonIconOnly)
    self.editor.setEffectNameOrder(['Paint', 'Erase', 'Draw'])
    self.editor.unorderedEffectsVisible = False
    self.editor.findChild(qt.QPushButton, "AddSegmentButton").hide()
    self.editor.findChild(qt.QPushButton, "RemoveSegmentButton").hide()
    self.editor.findChild(ctk.ctkMenuButton, "Show3DButton").hide()
    self.editor.findChild(ctk.ctkExpandableWidget, "SegmentsTableResizableFrame").hide()
    self._updateFromData()

  def delete(self):
    self.editor.delete()

  def resetInteraction(self):
    self.editor.setActiveEffectByName("Selection")