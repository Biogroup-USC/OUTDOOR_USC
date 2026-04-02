from outdoor.user_interface.data.OutdoorDTO import OutdoorDTO


class ComponentEmissionDTO(OutdoorDTO):
    """
    DTO to store LCA emission/impact data for chemical components.
    This DTO is paired with ComponentDTO and stores independently.
    """
    def __init__(self, rowposition: int, uid: str, name: str = ""):
        super().__init__()
        self.rowPosition = rowposition
        self.uid = uid
        self.name = name
        self.calculated = False
        # LCA impacts dictionary: {impact_category: value}
        self.impacts = {}
        # Store the LCA exchanges data similar to ComponentDTO
        self.LCA = {
            'exchanges': {},
            'metadata': {}
        }

    def __getitem__(self, item):
        match item:
            case 0:
                return self.name
            case 1:
                return self.uid
            case _:
                return self

    def as_dict(self):
        """Convert DTO to dictionary for serialization"""
        d = {
            "uuid": self.uid,
            "rowPosition": self.rowPosition,
            "name": self.name,
            "calculated": self.calculated,
            "impacts": self.impacts,
            "LCA": self.LCA,
        }
        return d

    def updateRow(self):
        """Update row position when rows are deleted"""
        self.rowPosition -= 1

    def updateField(self, field, value):
        """Update a field in the DTO"""
        match field:
            case "rowPosition":
                self.rowPosition = value
            case "name":
                self.name = value
            case "calculated":
                self.calculated = value
            case "impacts":
                self.impacts = value
            case "LCA":
                self.LCA = value
