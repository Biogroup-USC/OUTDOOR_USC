import logging
#import bw2calc as bc

class OutdoorDTO(object):
    name: str
    uid: str
    LCA: dict
    calculated: bool # to change the color of the button in the GUI

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.LCA = {'Results': {},
                    'exchanges':{}}



        self.emptyCategories = {
            'terrestrial acidification potential (TAP)': 0,
            'global warming potential (GWP100)': 0,
            'freshwater ecotoxicity potential (FETP)': 0,
            'marine ecotoxicity potential (METP)': 0,
            'terrestrial ecotoxicity potential (TETP)': 0,
            'fossil fuel potential (FFP)': 0,
            'freshwater eutrophication potential (FEP)': 0,
            'marine eutrophication potential (MEP)': 0,
            'human toxicity potential (HTPc)': 0,
            'human toxicity potential (HTPnc)': 0,
            'ionising radiation potential (IRP)': 0,
            'agricultural land occupation (LOP)': 0,
            'surplus ore potential (SOP)': 0,
            'ozone depletion potential (ODPinfinite)': 0,
            'particulate matter formation potential (PMFP)': 0,
            'photochemical oxidant formation potential: humans (HOFP)': 0,
            'photochemical oxidant formation potential: ecosystems (EOFP)': 0,
            'water consumption potential (WCP)': 0,
            'ecosystem quality': 0,
            'human health': 0,
            'natural resources': 0
        }

        pass

    def getLCAImpacts(self) -> dict:
        if self.calculated:
            return  self.LCA['Results']
        else:
            return {}
