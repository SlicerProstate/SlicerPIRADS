import vtk
import slicer

from SlicerDevelopmentToolboxUtils.mixins import ParameterNodeObservationMixin


class AnnotationFactory(object):

  @staticmethod
  def getAnnotationClassForMRMLNodeClass(mrmlNodeClass):
    if mrmlNodeClass == "vtkMRMLSegmentationNode":
      return Segmentation
    return None


class Annotation(ParameterNodeObservationMixin):

  DataChangedEvent = vtk.vtkCommand.UserEvent + 201
  MRML_NODE_CLASS = None

  def __init__(self, volumeNode):
    if not self.MRML_NODE_CLASS:
      raise ValueError("MRML_NODE_CLASS needs to be defined for all inheriting classes of {}".format(self.__class__.__name__))
    self._volumeNode = volumeNode
    self.mrmlNode = slicer.mrmlScene.AddNewNodeByClass(self.MRML_NODE_CLASS)

  def delete(self):
    if self.mrmlNode:
      slicer.mrmlScene.RemoveNode(self.mrmlNode)


class Segmentation(Annotation):

  MRML_NODE_CLASS = "vtkMRMLSegmentationNode"

  def __init__(self, volumeNode):
    super(Segmentation, self).__init__(volumeNode)
    self._createAndObserveSegment()

  def _createAndObserveSegment(self):
    import vtkSegmentationCorePython as vtkSegmentationCore
    segment = vtkSegmentationCore.vtkSegment()
    segment.SetName(self._volumeNode.GetName())
    # TODO need to think about the reference more in detail. After loading the volume nodes don't occupy the same address
    self.mrmlNode.SetReferenceImageGeometryParameterFromVolumeNode(self._volumeNode)
    self.mrmlNode.GetSegmentation().AddSegment(segment)
    self.mrmlNode.AddObserver(vtkSegmentationCore.vtkSegmentation.SegmentModified, self._onSegmentModified)

  # def setName(self, name):
  #   return self.mrmlNode.GetSegmentation().GetNthSegment(0).SetName(name)
  #
  # def getName(self):
  #   return self.mrmlNode.GetSegmentation().GetNthSegment(0).GetName()

  def _onSegmentModified(self, caller, event):
    self.invokeEvent(self.DataChangedEvent)