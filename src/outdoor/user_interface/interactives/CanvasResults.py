import logging
import uuid
import re
from copy import deepcopy

from PyQt5.QtCore import QRectF, Qt, QPointF, QPoint
from PyQt5.QtGui import QPainter, QPen, QColor, QPainterPath, QFont, QPainterPathStroker, QKeySequence
from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsEllipseItem, QGraphicsObject, QGraphicsItem, \
    QApplication, QGraphicsPathItem

from outdoor.user_interface.data.ProcessDTO import ProcessDTO, ProcessType, UpdateField
from outdoor.user_interface.dialogs.GeneratorDialog import GeneratorDialog
from outdoor.user_interface.dialogs.InputParametersDialog import InputParametersDialog
from outdoor.user_interface.dialogs.LCADialog import LCADialog
from outdoor.user_interface.dialogs.OutputParametersDialog import OutputParametersDialog
from outdoor.user_interface.dialogs.PhysicalProcessDialog import PhysicalProcessesDialog
from outdoor.user_interface.dialogs.StoichiometricReactorDialog import StoichiometricReactorDialog
from outdoor.user_interface.dialogs.YieldReactorDialog import YieldReactorDialog


class CanvasResults(QGraphicsView):
    """
    A widget (QGraphicsView) for the right panel where icons can be dropped onto it. Here is where the user can create
    the superstructure by dragging and dropping icons from the left panel. This class also handles the connections between
    the icons.
    """

    def __init__(self, centralDataManager, signalManager, iconLabels):
        super().__init__()
        # set up the logger
        self.logger = logging.getLogger(__name__)
        # Store the icon data managers for use in the widget
        self.centralDataManager = centralDataManager
        self.signalManager = signalManager

        # store the icon labels
        self.iconLabels = iconLabels
        # Set up the scene for scalable graphics
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)  # For better visual quality
        # Enable drag and drop events
        self.setAcceptDrops(True)
        # To keep a reference to the currently selected icon
        self.selectedElement = None

        self.setStyleSheet("background-color: white;")
        self.iconData = {}  # Add this line to store dialog data

        # initiate copy and paste variables
        self.positionCopy = None
        self.itemName = None
        self.dtoIconCopy = None

        # add index to icons according to the type of icon:
        # use UUIDs for the indexs!
        self.index_input = []
        self.index_process = []
        self.index_split = []
        self.index_output = []
        self.UUID = None

        # track the start and end points of the line
        self.startPoint = None
        self.endPoint = None
        self.currentLine = None
        self.drawingLine = False
        self.endPort = None
        self.startPort = None

        self.setMouseTracking(True)  # Enable mouse tracking

        # Define scale factors for zooming
        self.zoomInFactor = 1.25  # Zoom in factor (25% larger)
        self.zoomOutFactor = 1 / self.zoomInFactor  # Zoom out factor (inverse of zoom in)
        self.scaleFactor = 1.0  # Initial scale factor

        # Variables for panning (dragging over the canvas)
        self.setDragMode(QGraphicsView.NoDrag)
        self.isPanning = False
        self.lastPanPoint = None

        # import the icons to the canvas if data is loaded from a file
        #self.importData()
