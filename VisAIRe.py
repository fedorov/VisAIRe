import os, re, string
import unittest
from __main__ import vtk, qt, ctk, slicer

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

  def setup(self):
    # Instantiate and connect widgets ...

    # reload button
    # (use this during development, but remove it when delivering
    #  your module to users)
    #self.reloadButton = qt.QPushButton("Reload")
    #self.reloadButton.toolTip = "Reload this module."
    #self.reloadButton.name = "VisAIRe Reload"
    #self.layout.addWidget(self.reloadButton)
    #self.reloadButton.connect('clicked()', self.onReload)

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
    for i in range(20):
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
    self.layoutNode = slicer.mrmlScene.GetNodesByClass('vtkMRMLLayoutNode').GetItemAsObject(0)
    self.layoutNode.AddLayoutDescription(123,compareViewTwoRows)
    self.layoutNode.SetViewArrangement(123)
    sliceCompositeNodes = slicer.mrmlScene.GetNodesByClass('vtkMRMLSliceCompositeNode')
    sliceNodes = slicer.mrmlScene.GetNodesByClass('vtkMRMLSliceNode')
    self.compare0 = None
    self.compare1 = None
    for i in range(sliceCompositeNodes.GetNumberOfItems()):
      scn = sliceCompositeNodes.GetItemAsObject(i)
      sn = sliceNodes.GetItemAsObject(i)
      print 'Composite node: ',sn.GetName()
      if sn.GetName() == 'Compare0':
        self.compare0 = scn
      if sn.GetName() == 'Compare1':
        self.compare1 = scn
  
  def onOpacityChangeRequested(self,value):
    print value
    self.compare0.SetForegroundOpacity(value)
    self.compare1.SetForegroundOpacity(value)

  def entrySelected(self, name):
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
    self.compare0.SetLinkedControl(False)
    self.compare1.SetLinkedControl(False)
    self.compare0.SetForegroundVolumeID(self.movingVolume.GetID())
    self.compare1.SetForegroundVolumeID(self.registeredVolumes[int(name)].GetID())
    self.compare0.SetLinkedControl(True)
    self.compare1.SetLinkedControl(True)
    self.compare0.SetBackgroundVolumeID(self.fixedVolumes[int(name)].GetID())
    self.compare1.SetBackgroundVolumeID(self.fixedVolumes[int(name)].GetID())
  
  def onConfigFileSelected(self):
    if not self.configFile:
      fileName = qt.QFileDialog.getOpenFileName(self.parent, "Choose assessment for configuration file","/","Conf Files (*.conf)")
    else:
      lastDir = self.configFile[0:string.rfind(self.configFile,'/')]
      fileName = qt.QFileDialog.getOpenFileName(self.parent, "Choose assessment for configuration file",lastDir,"Conf Files (*.conf)")

    if fileName == '':
      return
    
    self.configFile = fileName
    try:
      label = string.split(fileName,'/')[-1]
    except:
      label = fileName
    self.configFilePicker.text = label

    # parse config file and load all of the volumes referenced
    slicer.mrmlScene.Clear(0)
    self.clearForm()
    self.fixedVolumes = []
    self.registeredVolumes = []
    self.movingVolume = None
    configFile = open(fileName,'r')
    mode = None
    for line in configFile:
      # drop newline
      line = line[:-1]
      m = re.match('\[(.*)\]',line)
      if m:
        mode = m.groups()[0]
        print('Parsing mode: '+mode)
        continue
      if mode:
        if mode == 'MovingImage':
          print('Will load movingVolume <'+line+'>')
          self.movingVolume = slicer.util.loadVolume(line,returnNode=True)[1]
        elif mode == 'FixedImages':
          self.fixedVolumes.append(slicer.util.loadVolume(line,returnNode=True)[1])
        elif mode == 'RegisteredImages':
          self.registeredVolumes.append(slicer.util.loadVolume(line,returnNode=True)[1])
        #elif mode == 'AssessmentQuestions':
        #  item = string.split(line,';')
        #  self.questions[item[0]] = item[1]
        elif mode == 'CaseName':
          self.caseName = line
          self.evaluationFrame.text = "Assessment Form for "+line
    
    # populate the assessment form    
    for fv in range(len(self.fixedVolumes)):
      self.formEntries[fv].visible = True
      self.formEntries[fv].text = self.fixedVolumes[fv].GetName()

    self.entrySelected('0')

  def clearForm(self):
    for i in range(20):
      self.formEntries[i].visible = False

    '''
    l = self.evaluationFrameLayout
    print('clearForm()')
    children = l.children()
    print children
    for i in range(1,len(children)):
      children[i].deleteLater()

    while l.count():
      i = l.takeAt(0)
      w = None
      if i:
        w = i.widget()
      if w:
        w.visible = False
        w.deleteLater()
    child = None
    try:
      child = self.evaluationFrame.children()[1]
    except:
      pass
    while child:
      print 'Will try to delete ',child
      child.deleteLater()
      qt.QApplication.processEvents()
      child = self.evaluationFrame.children()[1]
      #self.timer.start()
    #else:
      #self.timer.stop()
    '''
      
  def onDoneButtonClicked(self):
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
