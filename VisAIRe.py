import os, re, string
import unittest
from __main__ import vtk, qt, ctk, slicer
import ConfigParser as config

from Editor import EditorWidget
from EditorLib import EditColor
import Editor
from EditorLib import EditUtil
from EditorLib import EditorLib

#
# VisAIRe
#

class VisAIRe:
  def __init__(self, parent):
    parent.title = "VisAIRe" # TODO make this more human readable by adding spaces
    parent.categories = [""]
    parent.dependencies = []
    parent.contributors = ["Andrey Fedorov"] # replace with "Firstname Lastname (Org)"
    parent.helpText = """
    Visual Assessment of Image Registration
    """
    parent.acknowledgementText = """
    Acks
    """ # replace with organization, grant and thanks.
    self.parent = parent

    # Add this test to the SelfTest module's list for discovery when the module
    # is created.  Since this module may be discovered before SelfTests itself,
    # create the list if it doesn't already exist.
    try:
      slicer.selfTests
    except AttributeError:
      slicer.selfTests = {}
    slicer.selfTests['VisAIRe'] = self.runTest

  def runTest(self):
    tester = VisAIReTest()
    tester.runTest()

#
# qVisAIReWidget
#

class VisAIReWidget:
  def __init__(self, parent = None):
    if not parent:
      self.parent = slicer.qMRMLWidget()
      self.parent.setLayout(qt.QVBoxLayout())
      self.parent.setMRMLScene(slicer.mrmlScene)
    else:
      self.parent = parent
    self.layout = self.parent.layout()
    if not parent:
      self.setup()
      self.parent.show()

    # TODO: figure out why module/class hierarchy is different
    # between developer builds ans packages
    try:
      # for developer build...
      self.editUtil = EditorLib.EditUtil.EditUtil()
    except AttributeError:
      # for release package...
      self.editUtil = EditorLib.EditUtil()

  def setup(self):
    self.viewMode = 'compare'
    self.compare0 = None
    self.compare1 = None
    self.sidebyside0 = None
    self.sidebyside1 = None

    # Instantiate and connect widgets ...

    # reload button
    # (use this during development, but remove it when delivering
    #  your module to users)
    self.reloadButton = qt.QPushButton("Reload")
    self.reloadButton.toolTip = "Reload this module."
    self.reloadButton.name = "VisAIRe Reload"
    self.layout.addWidget(self.reloadButton)
    self.reloadButton.connect('clicked()', self.onReload)

    # reload and test button
    # (use this during development, but remove it when delivering
    #  your module to users)
    #self.reloadAndTestButton = qt.QPushButton("Reload and Test")
    #self.reloadAndTestButton.toolTip = "Reload this module and then run the self tests."
    #self.layout.addWidget(self.reloadAndTestButton)
    #self.reloadAndTestButton.connect('clicked()', self.onReloadAndTest)

    # entry for the rater name
    label = qt.QLabel('Rater name:')
    self.raterName = qt.QLineEdit()
    self.layout.addWidget(label)
    self.layout.addWidget(self.raterName)

    # Configuration file picker
    label = qt.QLabel('Configuration file:')
    self.configFilePicker = qt.QPushButton('N/A')
    self.configFilePicker.connect('clicked()',self.onConfigFileSelected)
    self.layout.addWidget(label)
    self.layout.addWidget(self.configFilePicker)

    self.makeSnapshots = qt.QPushButton('Make snapshots')
    self.layout.addWidget(self.makeSnapshots)
    self.makeSnapshots.connect('clicked()', self.onMakeSnapshots)

    # Opacity control
    label = qt.QLabel('Foreground/Background opacity:')
    self.opacitySlider = ctk.ctkSliderWidget()
    self.opacitySlider.connect('valueChanged(double)',self.onOpacityChangeRequested)
    self.opacitySlider.minimum = 0.
    self.opacitySlider.maximum = 1.
    self.opacitySlider.decimals = 1
    self.opacitySlider.singleStep = 0.1
    self.layout.addWidget(label)
    self.layout.addWidget(self.opacitySlider)

    #  Button to switch between showing background/foreground volumes
    self.bgfgButton = qt.QPushButton("Switch Background/Foreground")
    self.layout.addWidget(self.bgfgButton)
    self.bgfgButton.connect('clicked()', self.onbgfgButtonPressed)

    # Select between compare view and editing layouts
    groupLabel = qt.QLabel('Review mode:')
    self.viewGroup = qt.QButtonGroup()
    self.compareSelector = qt.QRadioButton('Compare view')
    self.sideBySideSelector = qt.QRadioButton('Side by side')
    self.compareSelector.setChecked(1)
    self.viewGroup.addButton(self.compareSelector,1)
    self.viewGroup.addButton(self.sideBySideSelector,2)
    self.groupWidget = qt.QWidget()
    self.groupLayout = qt.QFormLayout(self.groupWidget)
    self.groupLayout.addRow(self.compareSelector, self.sideBySideSelector)
    self.layout.addWidget(self.groupWidget)
    # step4Layout.addRow(groupLabel, self.viewGroup)

    self.viewGroup.connect('buttonClicked(int)', self.onViewUpdateRequested)

    # setup Editor widget
    editorWidgetParent = slicer.qMRMLWidget()
    editorWidgetParent.setLayout(qt.QVBoxLayout())
    editorWidgetParent.setMRMLScene(slicer.mrmlScene)
    self.editorWidget = EditorWidget(parent=editorWidgetParent,showVolumesFrame=False)
    self.editorWidget.setup()
    self.editorParameterNode = self.editUtil.getParameterNode()
    self.layout.addWidget(editorWidgetParent)

    # Slice control
    #label = qt.QLabel('Slice selector:')
    #self.sliceSlider = ctk.ctkSliderWidget()
    #self.sliceSlider.connect('valueChanged(double)',self.onSliceChangeRequested)
    #self.sliceSlider.minimum = 0.
    #self.sliceSlider.maximum = 1.
    #self.sliceSlider.decimals = 1
    #self.sliceSlider.singleStep = 0.1
    #self.layout.addWidget(label)
    #self.layout.addWidget(self.opacitySlider)

    # Collapsible button to keep the content of the form
    self.evaluationFrame = ctk.ctkCollapsibleButton()
    self.evaluationFrame.text = "Assessment Form"
    self.evaluationFrame.collapsed = 0
    self.evaluationFrameLayout = qt.QFormLayout(self.evaluationFrame)
    self.layout.addWidget(self.evaluationFrame)

    self.formEntries = []
    self.questions = {'Improved compared to non-registered?':'binary','Diagnostic quality?':'binary','Error quantification (if available)':'numeric'}
    self.formEntryMapper = qt.QSignalMapper()
    self.formEntryMapper.connect('mapped(const QString&)', self.entrySelected)

    self.maxFormEntries = 30
    for i in range(self.maxFormEntries):
    # populate the assessment form
      # create a new sub-frame with the questions
      cb = ctk.ctkCollapsibleButton()
      cb.visible = False
      cb.collapsed = True
      self.formEntries.append(cb)
      self.formEntryMapper.setMapping(cb, str(i))
      cb.connect('contentsCollapsed(bool)', self.formEntryMapper, 'map()')

      layout = qt.QFormLayout(cb)
      self.evaluationFrameLayout.addRow(cb)

      for (q,c) in self.questions.items():
        if c == 'binary':
          self.addBinaryEntry(q, layout)
        elif c == 'numeric':
          self.addNumericEntry(q, layout)


    # Save button
    self.doneButton = qt.QPushButton("Save")
    self.doneButton.toolTip = "Click this when done."
    self.layout.addWidget(self.doneButton)
    self.doneButton.connect('clicked(bool)', self.onDoneButtonClicked)

    # Add vertical spacer
    self.layout.addStretch(1)

    # Initialize internal persistent variables
    self.configFile = None
    self.movingVolume = None
    self.perVolumeForms = []
    self.fixedVolumes = []
    self.registeredVolumes = []
    self.transforms = []
    self.caseName = None


    # add custom layout for comparing two pairs of volumes
    compareViewTwoRows ="<layout type=\"vertical\">"
    for i in range(2):
      compareViewTwoRows = compareViewTwoRows+"   <item>\
    <view class=\"vtkMRMLSliceNode\" singletontag=\"Compare"+str(i)+"\">\
    <property name=\"orientation\" action=\"default\">Axial</property>\
    <property name=\"viewlabel\" action=\"default\">"+str(i)+"</property>\
    <property name=\"viewcolor\" action=\"default\">#E17012</property>\
    <property name=\"lightboxrows\" action=\"default\">1</property>\
    <property name=\"lightboxcolumns\" action=\"default\">6</property>\
    <property name=\"lightboxrows\" action=\"relayout\">1</property>\
    <property name=\"lightboxcolumns\" action=\"relayout\">6</property>\
    </view>\
    </item>"
    compareViewTwoRows = compareViewTwoRows+"</layout>"

    sideBySide = "<layout type=\"horizontal\">\
     <item>\
      <view class=\"vtkMRMLSliceNode\" singletontag=\"SideBySide0\">\
       <property name=\"orientation\" action=\"default\">Axial</property>\
       <property name=\"viewlabel\" action=\"default\">Moving</property>\
       <property name=\"viewcolor\" action=\"default\">#F34A33</property>\
      </view>\
     </item>\
     <item>\
      <view class=\"vtkMRMLSliceNode\" singletontag=\"SideBySide1\">\
       <property name=\"orientation\" action=\"default\">Axial</property>\
       <property name=\"viewlabel\" action=\"default\">Reference</property>\
       <property name=\"viewcolor\" action=\"default\">#EDD54C</property>\
      </view>\
     </item>\
    </layout>"
    print(sideBySide)

    layoutNodes = slicer.mrmlScene.GetNodesByClass('vtkMRMLLayoutNode')
    layoutNodes.SetReferenceCount(layoutNodes.GetReferenceCount()-1)
    self.layoutNode = layoutNodes.GetItemAsObject(0)
    self.CompareLayout = 123
    self.ContouringLayout = 124
    self.layoutNode.AddLayoutDescription(self.CompareLayout,compareViewTwoRows)
    self.layoutNode.AddLayoutDescription(self.ContouringLayout,sideBySide)
    self.layoutNode.SetViewArrangement(self.ContouringLayout)
    self.layoutNode.SetViewArrangement(self.CompareLayout)
    sliceCompositeNodes = slicer.mrmlScene.GetNodesByClass('vtkMRMLSliceCompositeNode')
    sliceCompositeNodes.SetReferenceCount(sliceCompositeNodes.GetReferenceCount()-1)
    sliceNodes = slicer.mrmlScene.GetNodesByClass('vtkMRMLSliceNode')
    sliceNodes.SetReferenceCount(sliceNodes.GetReferenceCount()-1)
    for i in range(sliceCompositeNodes.GetNumberOfItems()):
      scn = sliceCompositeNodes.GetItemAsObject(i)
      sn = sliceNodes.GetItemAsObject(i)
      sn.SetUseLabelOutline(1)
      if sn.GetName() == 'Compare0':
        self.compare0 = scn
      if sn.GetName() == 'Compare1':
        self.compare1 = scn
      if sn.GetName() == 'SideBySide0':
        self.sidebyside0 = scn
      if sn.GetName() == 'SideBySide1':
        self.sidebyside1 = scn

  def compositeNodeForWidget(self,name):
    sliceCompositeNodes = slicer.mrmlScene.GetNodesByClass('vtkMRMLSliceCompositeNode')
    sliceCompositeNodes.SetReferenceCount(sliceCompositeNodes.GetReferenceCount()-1)
    sliceNodes = slicer.mrmlScene.GetNodesByClass('vtkMRMLSliceNode')
    sliceNodes.SetReferenceCount(sliceNodes.GetReferenceCount()-1)
    for i in range(sliceCompositeNodes.GetNumberOfItems()):
      scn = sliceCompositeNodes.GetItemAsObject(i)
      sn = sliceNodes.GetItemAsObject(i)
      sn.SetUseLabelOutline(1)
      if sn.GetName() == name:
        return scn
    return None

  def onViewUpdateRequested(self,id):
    if id == 1:
      self.viewMode = 'compare'
    if id == 2:
      self.viewMode = 'sidebyside'
    self.entrySelected('0')

  def onOpacityChangeRequested(self,value):
    if self.viewMode == 'compare':
      viewer0 = self.compare0
      viewer1 = self.compare1
    else:
      viewer0 = self.sidebyside0
      viewer1 = self.sidebyside1

    if viewer0:
      viewer0.SetForegroundOpacity(value)
    if viewer1:
      viewer1.SetForegroundOpacity(value)

  def onbgfgButtonPressed(self):
    if self.viewMode == 'compare':
      viewer0 = self.compare0
      viewer1 = self.compare1
    else:
      viewer0 = self.sidebyside0
      viewer1 = self.sidebyside1

    if viewer0.GetForegroundOpacity() == 1:
      viewer0.SetForegroundOpacity(0)
      viewer1.SetForegroundOpacity(0)
    else:
      viewer0.SetForegroundOpacity(1)
      viewer1.SetForegroundOpacity(1)

  def onMakeSnapshots(self):
    for key in range(len(self.transforms)):
      print('Key :'+str(key))
      if not self.transforms[key]:
        continue
      self.makeSnapshotsForKey(key)

  def makeSnapshotsForKey(self,name,snapshots=True):
      movingID = self.movingVolume.GetID()
      registeredID = self.registeredVolumes[int(name)].GetID()
      fixedID = self.fixedVolumes[int(name)].GetID()

      snapshotsDir = '/Users/fedorov/Temp/RegistrationSnapshots'
      # assume this is full path, and the file name has the format
      #  <CaseID>_<junk>
      caseId = os.path.split(self.configFileName)[-1].split('_')[0]

      redSliceCompositeNode = self.compositeNodeForWidget('Red')

      redSliceCompositeNode.SetForegroundOpacity(0)

      self.setupLightbox(fixedID,movingID)
      if snapshots:
        snapshotName = os.path.join(snapshotsDir,caseId+'_'+str(name)+'_fixed.png')
        self.makeSnapshot('Red',snapshotName)

      self.setupLightbox(registeredID,movingID)
      if snapshots:
        snapshotName = os.path.join(snapshotsDir,caseId+'_'+str(name)+'_registered.png')
        self.makeSnapshot('Red',snapshotName)

      # make snapshots of the moving image for the first one
      # (same for all keys)
      if str(name) == '0':
        redSliceCompositeNode.SetForegroundOpacity(1)
        if snapshots:
          snapshotName = os.path.join(snapshotsDir,caseId+'_moving.png')
          self.makeSnapshot('Red',snapshotName)

  def makeSnapshot(self, widgetName, snapshotName):
      w = slicer.app.layoutManager().sliceWidget(widgetName)
      if w:
        qt.QPixmap().grabWidget(w).toImage().save(snapshotName)

  def setupSliceWidget(self,swName):
      w = slicer.app.layoutManager().sliceWidget(swName)
      w.fitSliceToBackground()
      sn = self.compositeNodeForWidget(swName)
      sn.SetForegroundOpacity(0)
      n = w.sliceLogic().GetSliceNode()
      fov = n.GetFieldOfView()
      n.SetFieldOfView(fov[0]/2.,fov[1]/2.,fov[2]/2.)

  def entrySelected(self, name):

    # prepare fixed volume label, if it is not available
    if self.movingVolumeSeg and not self.fixedVolumesSegmentations[int(name)] and self.transforms[int(name)]:
      tfm = self.transforms[int(name)]
      print('Resampled segmentation is missing, but will resample with '+tfm.GetID())

      resample = slicer.modules.brainsresample
      volumesLogic = slicer.modules.volumes.logic()
      labelName = self.fixedVolumes[int(name)].GetName()+'-label'
      self.fixedVolumesSegmentations[int(name)] = volumesLogic.CreateAndAddLabelVolume(slicer.mrmlScene, self.fixedVolumes[int(name)], labelName)
      parameters = {}
      parameters['inputVolume'] = self.movingVolumeSeg.GetID()
      parameters['referenceVolume'] = self.fixedVolumes[int(name)].GetID()
      parameters['warpTransform'] = self.transforms[int(name)].GetID()
      parameters['outputVolume'] = self.fixedVolumesSegmentations[int(name)]
      parameters['pixelType'] = 'short'
      parameters['interpolationMode'] = 'NearestNeighbor'
      slicer.cli.run(resample, None, parameters, wait_for_completion = True)

      # initialize the file name for the segmentation
      storageNode = self.fixedVolumesSegmentations[int(name)].GetStorageNode()
      fixedVolumeIdStr = str(self.fixedVolumeIds[int(name)])
      segFileName = os.path.join(os.path.split(self.config.get('MovingData','Segmentation'))[0],fixedVolumeIdStr+'-label.nrrd')
      storageNode.SetFileName(segFileName)
      storageNode.SetWriteFileFormat('.nrrd')

      # update the config file to keep reference to the newly created
      # segmentation label
      self.config.set('FixedData','Segmentation'+fixedVolumeIdStr,segFileName)

      # setup the Editor
      self.editorWidget.setMasterNode(self.fixedVolumes[int(name)])
      self.editorWidget.setMergeNode(self.fixedVolumesSegmentations[int(name)])
      self.editorParameterNode.Modified()

    if self.viewMode == 'compare':
      self.layoutNode.SetViewArrangement(self.CompareLayout)
      viewer0 = self.compare0
      viewer1 = self.compare1
    else:
      self.layoutNode.SetViewArrangement(self.ContouringLayout)
      viewer0 = self.sidebyside0
      viewer1 = self.sidebyside1

    entry = self.formEntries[int(name)]
    if entry.collapsed == True:
      return

    print 'Entry selected: ',name
    for i in range(len(self.fixedVolumes)):
      #self.formEntries[i].blockSignals(True)
      if i == int(name):
        self.formEntries[i].collapsed = False
        continue
      else:
        self.formEntries[i].collapsed = True
      #self.formEntries[i].blockSignals(False)
    viewer0.SetLinkedControl(False)
    viewer1.SetLinkedControl(False)

    v0fgID = self.movingVolume.GetID()
    v1fgID = self.registeredVolumes[int(name)].GetID()
    bgID = self.fixedVolumes[int(name)].GetID()
    print('Will be setting ids: '+v0fgID+','+v1fgID+','+bgID)

    viewer0.SetForegroundVolumeID(v0fgID)
    if self.movingVolumeSeg:
      viewer0.SetLabelVolumeID(self.movingVolumeSeg.GetID())

    viewer1.SetForegroundVolumeID(v1fgID)
    # if segmentation is available for the registered node, display it
    if self.fixedVolumesSegmentations[int(name)]:
      viewer1.SetLabelVolumeID(self.fixedVolumesSegmentations[int(name)].GetID())
    # otherwise, if the transform is available, resample the moving volume
    # segmentation, populate the entry in the list of segmentations and
    # initialize the view


    viewer0.SetLinkedControl(True)
    viewer1.SetLinkedControl(True)
    viewer0.SetBackgroundVolumeID(bgID)
    viewer1.SetBackgroundVolumeID(bgID)

  def setupLightbox(self,fixedID,movingID):
    lm = slicer.app.layoutManager()
    lm.setLayout(6) # Red
    w = lm.sliceWidget('Red')
    cn = self.compositeNodeForWidget('Red')
    cn.SetForegroundVolumeID(movingID)
    cn.SetBackgroundVolumeID(fixedID)
    slicer.app.processEvents()
    sc = w.sliceController()
    sc.setLightbox(3,6)
    w.fitSliceToBackground()
    slider = sc.children()[1].children()[-1]
    n = w.sliceLogic().GetSliceNode()
    fov = n.GetFieldOfView()
    # zoom into the prostate region
    n.SetFieldOfView(fov[0]/2.5,fov[1]/2.5,fov[2])
    sc.setSliceOffsetValue(slider.minimum)

  def initializeViews(self, name):
    if self.viewMode == 'compare':
      self.layoutNode.SetViewArrangement(self.CompareLayout)
      viewer0 = self.compare0
      viewer1 = self.compare1
    else:
      self.layoutNode.SetViewArrangement(self.ContouringLayout)
      viewer0 = self.sidebyside0
      viewer1 = self.sidebyside1

    viewer0.SetLinkedControl(False)
    viewer1.SetLinkedControl(False)

    v0fgID = self.movingVolume.GetID()
    v1fgID = self.registeredVolumes[int(name)].GetID()
    bgID = self.fixedVolumes[int(name)].GetID()
    print('Will be setting ids: '+v0fgID+','+v1fgID+','+bgID)

    viewer0.SetForegroundVolumeID(v0fgID)
    if self.movingVolumeSeg:
      viewer0.SetLabelVolumeID(self.movingVolumeSeg.GetID())

    viewer1.SetForegroundVolumeID(v1fgID)
    # if segmentation is available for the registered node, display it
    if self.fixedVolumesSegmentations[int(name)]:
      viewer1.SetLabelVolumeID(self.fixedVolumesSegmentations[int(name)].GetID())
    # otherwise, if the transform is available, resample the moving volume
    # segmentation, populate the entry in the list of segmentations and
    # initialize the view


    viewer0.SetLinkedControl(True)
    viewer1.SetLinkedControl(True)
    viewer0.SetBackgroundVolumeID(bgID)
    viewer1.SetBackgroundVolumeID(bgID)


  def onConfigFileSelected(self):
    if not self.configFile:
      fileName = qt.QFileDialog.getOpenFileName(self.parent, "Choose assessment for configuration file","/","Conf Files (*.ini)")
    else:
      lastDir = self.configFile[0:string.rfind(self.configFile,'/')]
      fileName = qt.QFileDialog.getOpenFileName(self.parent, "Choose assessment for configuration file",lastDir,"Conf Files (*.ini)")

    if fileName == '':
      return

    self.configFile = fileName
    try:
      label = string.split(fileName,'/')[-1]
    except:
      label = fileName
    self.configFilePicker.text = label

    self.initFromFile(fileName)

  def initFromFile(self, fileName):
    # parse config file and load all of the volumes referenced
    slicer.mrmlScene.Clear(0)
    self.clearForm()
    self.fixedVolumes = []
    self.fixedVolumeIds = []
    self.registeredVolumes = []
    self.movingVolume = None
    self.movingVolumeSeg = None

    self.config = config.SafeConfigParser()
    cf = self.config
    cf.optionxform = str
    cf.read(fileName)
    self.configFileName = fileName

    assert cf.has_section('Info')
    assert cf.has_section('MovingData')
    assert cf.has_section('FixedData')
    assert cf.has_section('RegisteredData')

    # there should only be one moving image
    self.movingVolume = slicer.util.loadVolume(cf.get('MovingData','Image'),returnNode=True)[1]
    dn = self.movingVolume.GetDisplayNode()
    mwl = [dn.GetWindow(), dn.GetLevel()]

    # (optional) segmentation of the moving image
    print('Set moving volume seg')
    try:
      self.movingVolumeSeg = slicer.util.loadLabelVolume(cf.get('MovingData','Segmentation'),{},returnNode=True)[1]
      self.movingVolumeSeg.SetAttribute('LabelMap','1')
      self.movingVolumeSeg.GetDisplayNode().SetAndObserveColorNodeID('vtkMRMLColorTableNodeFileGenericAnatomyColors.txt')
      print('Setup color node: '+self.movingVolumeSeg.GetDisplayNode().GetColorNodeID())
    except:
      print(' ... to None')
      self.movingVolumeSeg = None

    # fixedVolumes: Slicer volume nodes corresponding to fixed images from the
    #   config file
    # fixedVolumeIds: Each volume appears as "Image<id>" in the config file;
    #   this list stores the ids assigned to the volumes
    # registeredVolumes: results of registration
    # transforms: transformations mapping moving volume to the corresponding
    #   fixed volume
    # fixedVolumesSegmentations: masks of a structure contoured in each of the
    #   fixed volumes
    # movingFiducials: fiducial points corresponding to image landmarks
    # fixedFiducials: fiducial points corresponding to the same landmarks in
    #   the fixed images

    # and an arbitrary number of fixed images
    fixedImageFiles = cf.options('FixedData')
    print(str(fixedImageFiles))
    for fi in fixedImageFiles:
      if re.match('Image\d+',fi):
        self.fixedVolumes.append(slicer.util.loadVolume(cf.get('FixedData',fi),returnNode=True)[1])
        fixedDisplNode = self.fixedVolumes[-1].GetDisplayNode()
        fixedDisplNode.SetAutoWindowLevel(0)
        fixedDisplNode.SetWindow(mwl[0])
        fixedDisplNode.SetLevel(mwl[1])
        self.fixedVolumeIds.append(fi.split('Image')[1])
    print('Fixed volumes: '+str(self.fixedVolumes))

    # (optional) segmentations of the structure in the fixed images
    self.registeredVolumes = [None] * len(self.fixedVolumes)
    self.fixedVolumesSegmentations = [None] * len(self.fixedVolumes)
    self.transforms = [None] * len(self.fixedVolumes)
    for fvId in range(len(self.fixedVolumes)):
      imageId = 'Image'+self.fixedVolumeIds[fvId]
      segId = 'Segmentation'+self.fixedVolumeIds[fvId]
      tfmId = 'Transform'+self.fixedVolumeIds[fvId]
      try:
        self.registeredVolumes[fvId] = slicer.util.loadVolume(cf.get('RegisteredData',imageId),{},returnNode=True)[1]
        registeredDisplNode = self.registeredVolumes[fvId].GetDisplayNode()
        registeredDisplNode.SetAutoWindowLevel(0)
        registeredDisplNode.SetWindow(mwl[0])
        registeredDisplNode.SetLevel(mwl[1])
      except:
        print('Failed to read RegisteredData/'+imageId)
        pass
      try:
        self.fixedVolumesSegmentations[fvId] = slicer.util.loadLabelVolume(cf.get('FixedData',segId),{},returnNode=True)[1]
      except:
        print('Failed to read FixedData/'+segId)
        pass
      #try:
      self.transforms[fvId] = slicer.util.loadTransform(cf.get('RegisteredData',tfmId),returnNode=True)[1]
      #except:
      #  print('Failed to read RegisteredData/'+tfmId)
      #  pass

    print('Number of fixed images: '+str(self.registeredVolumes))
    print('Number of transformations: '+str(self.transforms))
    print('Number of fixed image segmentations: '+str(self.fixedVolumesSegmentations))

    assert len(self.fixedVolumes) == len(self.registeredVolumes)

    self.caseName = cf.get('Info','CaseName')
    self.evaluationFrame.text = "Assessment Form for "+self.caseName

    # populate the assessment form
    for fv in range(len(self.fixedVolumes)):
      self.formEntries[fv].visible = True
      self.formEntries[fv].text = self.fixedVolumes[fv].GetName()

    # self.entrySelected('0')

  def clearForm(self):
    for i in range(self.maxFormEntries):
      self.formEntries[i].visible = False

  def onDoneButtonClicked(self):
    # save the config file
    self.config.write(open(self.configFileName,'w'))

    return

    path = self.configFile[0:string.rfind(self.configFile,'/')]
    reportName = path+'/'+self.caseName+'-'+self.raterName.text+'-report.log'
    report = open(reportName,'w')
    report.write(self.configFile+'\n')
    for i in range(len(self.fixedVolumes)):
      report.write(self.fixedVolumes[i].GetName()+';')
      item = 2
      print 'num children: ',len(self.formEntries[i].children())
      for (q,c) in self.questions.items():
        report.write(q+';')
        widget = self.formEntries[i].children()[item]
        print widget
        if c == 'binary':
          checked = str(int(widget.checked))
          report.write(str(checked)+';')
        elif c == 'numeric':
          error = str(widget.text)
          report.write(error+';')
        item = item+2
      report.write('\n')
    report.close()

  def addBinaryEntry(self,question,layout):
    self.questions[question] = 'binary'
    label = qt.QLabel(question)
    item = qt.QCheckBox()
    layout.addRow(label,item)
    #self.formEntries.append(item)

  def addNumericEntry(self,question,layout):
    self.questions[question] = 'numeric'
    label = qt.QLabel(question)
    item = qt.QLineEdit()
    layout.addRow(label,item)
    #self.formEntries.append(item)

  def onReload(self,moduleName="VisAIRe"):
    """Generic reload method for any scripted module.
    ModuleWizard will subsitute correct default moduleName.
    """
    import imp, sys, os, slicer

    widgetName = moduleName + "Widget"

    # reload the source code
    # - set source file path
    # - load the module to the global space
    filePath = eval('slicer.modules.%s.path' % moduleName.lower())
    p = os.path.dirname(filePath)
    if not sys.path.__contains__(p):
      sys.path.insert(0,p)
    fp = open(filePath, "r")
    globals()[moduleName] = imp.load_module(
        moduleName, fp, filePath, ('.py', 'r', imp.PY_SOURCE))
    fp.close()

    # rebuild the widget
    # - find and hide the existing widget
    # - create a new widget in the existing parent
    parent = slicer.util.findChildren(name='%s Reload' % moduleName)[0].parent()
    for child in parent.children():
      try:
        child.hide()
      except AttributeError:
        pass
    # Remove spacer items
    item = parent.layout().itemAt(0)
    while item:
      parent.layout().removeItem(item)
      item = parent.layout().itemAt(0)

    # delete the old widget instance
    '''
    widgetName = moduleName+'Widget'
    if hasattr(globals()['slicer'].modules, widgetName):
      getattr(globals()['slicer'].modules, widgetName).cleanup()
    '''

    # create new widget inside existing parent
    globals()[widgetName.lower()] = eval(
        'globals()["%s"].%s(parent)' % (moduleName, widgetName))
    globals()[widgetName.lower()].setup()

  def onReloadAndTest(self,moduleName="VisAIRe"):
    self.onReload()
    evalString = 'globals()["%s"].%sTest()' % (moduleName, moduleName)
    tester = eval(evalString)
    tester.runTest()

#
# VisAIReLogic
#

class VisAIReLogic:
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget
  """
  def __init__(self):
    pass

  def hasImageData(self,volumeNode):
    """This is a dummy logic method that
    returns true if the passed in volume
    node has valid image data
    """
    if not volumeNode:
      print('no volume node')
      return False
    if volumeNode.GetImageData() == None:
      print('no image data')
      return False
    return True


class VisAIReTest(unittest.TestCase):
  """
  This is the test case for your scripted module.
  """

  def delayDisplay(self,message,msec=1000):
    """This utility method displays a small dialog and waits.
    This does two things: 1) it lets the event loop catch up
    to the state of the test so that rendering and widget updates
    have all taken place before the test continues and 2) it
    shows the user/developer/tester the state of the test
    so that we'll know when it breaks.
    """
    print(message)
    self.info = qt.QDialog()
    self.infoLayout = qt.QVBoxLayout()
    self.info.setLayout(self.infoLayout)
    self.label = qt.QLabel(message,self.info)
    self.infoLayout.addWidget(self.label)
    qt.QTimer.singleShot(msec, self.info.close)
    self.info.exec_()

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear(0)

  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.test_VisAIRe1()

  def test_VisAIRe1(self):
    """ Ideally you should have several levels of tests.  At the lowest level
    tests sould exercise the functionality of the logic with different inputs
    (both valid and invalid).  At higher levels your tests should emulate the
    way the user would interact with your code and confirm that it still works
    the way you intended.
    One of the most important features of the tests is that it should alert other
    developers when their changes will have an impact on the behavior of your
    module.  For example, if a developer removes a feature that you depend on,
    your test should break so they know that the feature is needed.
    """

    self.delayDisplay("Starting the test")
    #
    # first, get some data
    #
    import urllib
    downloads = (
        ('http://slicer.kitware.com/midas3/download?items=5767', 'FA.nrrd', slicer.util.loadVolume),
        )

    for url,name,loader in downloads:
      filePath = slicer.app.temporaryPath + '/' + name
      if not os.path.exists(filePath) or os.stat(filePath).st_size == 0:
        print('Requesting download %s from %s...\n' % (name, url))
        urllib.urlretrieve(url, filePath)
      if loader:
        print('Loading %s...\n' % (name,))
        loader(filePath)
    self.delayDisplay('Finished with download and loading\n')

    volumeNode = slicer.util.getNode(pattern="FA")
    logic = VisAIReLogic()
    self.assertTrue( logic.hasImageData(volumeNode) )
    self.delayDisplay('Test passed!')
