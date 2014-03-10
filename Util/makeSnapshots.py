w=slicer.modules.VisAIReWidget

for c in range(84,100):
  f='/Users/fedorov/Documents/Projects (original)/BxRetrospectiveAccuracyEvaluation/RegistrationVisualVerification/Case'+str(c)+'_VisAIRe.ini'
  try:
    w.initFromFile(f)
  except:
    continue
  w.onMakeSnapshots()
