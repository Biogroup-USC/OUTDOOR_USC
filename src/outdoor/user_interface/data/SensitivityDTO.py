import logging
from outdoor.user_interface.data.OutdoorDTO import OutdoorDTO

class SensitivityDTO(OutdoorDTO):
    def __init__(self, rowPosition: int = None, uid: str = "",
                parameterType: str = "", unitUid: str = "", componentName: str = "",
                reactionUid: str = "", lowerBound: float = 0.0, upperBound: float = 0.0, steps: float = 0.0):

        # add the logger
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.rowPosition = rowPosition
        self.uid = uid
        self.parameterType = parameterType
        self.unitUid = unitUid
        self.targetUnitProcess = ""
        self.componentName = componentName
        self.reactionUid = reactionUid
        self.lowerBound = lowerBound
        self.upperBound = upperBound
        self.steps = steps

    def as_dict(self):
        d = {
            "uuid": self.uid,
            "rowPosition": self.rowPosition,
            "parameterType": self.parameterType,
            "unitUid": self.unitUid,
            "targetUnitProcess": self.targetUnitProcess,
            "componentName": self.componentName,
            "reactionUid": self.reactionUid,
            "lowerBound": self.lowerBound,
            "upperBound": self.upperBound,
            "steps": self.steps,
        }
        return d

    def updateRow(self):
        self.rowPosition -= 1

    def upadateField(self, field, value):
        match field:
            case "rowPosition":
                self.rowPosition = value
            case "parameterType":
                self.parameterType = value
            case "unitUid":
                self.unitUid = value
            case "componentName":
                self.componentName = value
            case "targetUnitProcess":
                self.targetUnitProcess = value
            case "reactionUid":
                self.reactionUid = value

            case "lowerBound":
                self.lowerBound = value

                #if value == '':
                #    self.lowerBound = 0
                #else:
                #    self.lowerBound = float(value)

            case "upperBound":
                self.upperBound = value
                # if value == '':
                #     self.upperBound = 0
                # else:
                #     self.upperBound = float(value)

            case "steps":
                self.steps = value

                # if value == '':
                #     self.steps = 0
                # else:
                #     self.steps = float(value)

