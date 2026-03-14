import logging
import uuid
import re
from copy import deepcopy

from PyQt5.QtCore import QRectF, Qt, QPointF, QPoint
from PyQt5.QtGui import QPainter, QPen, QColor, QPainterPath, QFont, QPainterPathStroker, QKeySequence
from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsEllipseItem, QGraphicsObject, QGraphicsItem, \
    QApplication, QGraphicsPathItem

from outdoor.user_interface.data.ProcessDTO import ProcessType
from outdoor.user_interface.interactives.Canvas import MovableIcon, InteractiveLine, ControlPoint, IconPort


class CanvasResults(QGraphicsView):
    """
    A widget (QGraphicsView) for the right panel where icons can be dropped onto it. Here is where the user can create
    the superstructure by dragging and dropping icons from the left panel. This class also handles the connections between
    the icons.
    """

    def __init__(self, centralDataManager, signalManager):
        super().__init__()
        # set up the logger
        self.logger = logging.getLogger(__name__)
        # Store the icon data managers for use in the widget
        self.centralDataManager = centralDataManager
        self.signalManager = signalManager

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

        # import the icons to the canvas if data is loaded from the output file
        #self.loadInResults(chosenUnits)

        # add label so we know which canvas is which
        self.scene.setProperty("canvas_id", "canvasResults")  # or "canvas2" for the second canvas
        self.scene.setSceneRect(-100000, -100000, 200000, 200000)

    def wheelEvent(self, event):
        # Get the angle delta of the wheel event
        angleDelta = event.angleDelta().y()
        if angleDelta > 0:
            # Wheel scrolled up, zoom in
            self.scaleView(self.zoomInFactor)
        else:
            # Wheel scrolled down, zoom out
            self.scaleView(self.zoomOutFactor)

    def scaleView(self, scaleFactor):
        # Apply the scale factor to the view
        factor = self.transform().scale(scaleFactor, scaleFactor).mapRect(QRectF(0, 0, 1, 1)).width()
        if factor < 0.07 or factor > 100:
            # Prevent zooming out too much or zooming in too much
            return

        self.scale(scaleFactor, scaleFactor)
        self.scaleFactor *= scaleFactor

    def dragEnterEvent(self, e):
        #print('Iniciate dragging icon')
        e.accept()

    def dragMoveEvent(self, event):
        #print("Drag Move Event")
        event.accept()

    def dropEvent(self, event):
        self.logger.debug('dropped icon')
        mimeData = event.mimeData()
        if mimeData.hasText():
            # Extract the necessary information from the MIME data
            text = mimeData.text()
            position = event.pos()
            scenePos = self.mapToScene(position)
            # get the correct icon type based on the text
            icon = self.createMovableIcon(text, event.pos())

            # Set the icon's position to the mouse cursor's position
            icon.setPos(scenePos)
            self.scene.addItem(icon)  # Add the created icon to the scene
            event.accept()

    def createMovableIcon(self, text, position, processType=None):
        """
        This method should create a new instance of MovableIcon or similar class based on the text
        :param text: (string) The text of the icon to identify the type
        :param position: QPoint position of the mouse click
        :param processType: type of icon from the Class ProcessType
        :return:
        """

        # Mapping of text to icon_type and index
        icon_map = {
            "Boolean Distributor": (ProcessType.BOOLDISTRIBUTOR, self.index_split),
            "Distributor": (ProcessType.DISTRIBUTOR, self.index_split),

            "Input": (ProcessType.INPUT, self.index_input),
            "Output": (ProcessType.OUTPUT, self.index_output),
            "LCA": (ProcessType.LCA, self.index_process),

            "Physical Process": (ProcessType.PHYSICAL, self.index_process),
            "Stoichiometric Reactor": (ProcessType.STOICHIOMETRIC, self.index_process),
            "Yield Reactor": (ProcessType.YIELD, self.index_process),

            "Generator": (ProcessType.GEN_ELEC, self.index_process),
        }

        # Check if the text is in the icon_map
        try:
            if text in icon_map or isinstance(text, ProcessType):
                if processType:
                    icon_type = text
                    index_list = self.index_process
                else:
                    icon_type, index_list = icon_map[text]

                # Create unique UUID
                UUID = uuid.uuid4().__str__()
                index_list.append(UUID)
                # Create MovableIcon
                iconWidget = MovableIcon(text=icon_type, centralDataManager=self.centralDataManager,
                                         signalManager=self.signalManager, iconID=UUID,
                                         icon_type=icon_type, position=position)

                iconWidget.setPos(self.mapToScene(position))
                return iconWidget

        except Exception as e:
            # Raise error if the icon type is not recognized
            self.logger.error("Could not place the processing block to the "
                              "canvas with Icon type {}".format(text))
            self.logger.error(e)

    def mouseMoveEvent(self, event):
        if self.currentLine is not None:
            # Map the mouse position to scene coordinates
            scenePos = self.mapToScene(event.pos())
            # Update the current line's endpoint to follow the mouse
            # This is where you need to adjust for the InteractiveLine class
            self.currentLine.endPoint = scenePos
            self.currentLine.updateAppearance()  # Redraw the line with the new end point

            # If you have any other behavior when moving the mouse, handle it here
        else:
            # Not drawing a line, so pass the event to the base class
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton or event.button() == Qt.LeftButton:
            self.setDragMode(QGraphicsView.NoDrag)
            self.setCursor(Qt.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def mousePressEvent(self, event):
        """
        This method is called when the mouse is pressed in the canvas. It is used to deselect icons and lines when
        pressing on an empty space in the canvas.
        :param event: click event
        :return: updates the selected element
        """
        item = self.itemAt(event.pos())

        if isinstance(item, ControlPoint):
            pass
        elif isinstance(item, IconPort): # or isinstance(item, TriangleIconPorts) or
            pass

        elif isinstance(item, MovableIcon):
            if self.selectedElement is not None and self.selectedElement != item:
                # If there is a previously selected icon and it's not the current item, reset its pen
                self.selectedElement.pen = QPen(Qt.black, 1)

                if isinstance(self.selectedElement, InteractiveLine):
                    self.selectedElement.setSelectedLine(
                        False)  # switch off visibility of the control point for the line
                    self.selectedElement.updateAppearance()

                else:
                    self.selectedElement.update()

            # Update the currently selected icon
            self.selectedElement = item

        elif isinstance(item, InteractiveLine):
            if self.selectedElement is not None and self.selectedElement != item:
                # If there is a previously selected icon and it's not the current item, reset its pen
                self.selectedElement.pen = QPen(Qt.black, 1)
                if isinstance(self.selectedElement, InteractiveLine):
                    self.selectedElement.setSelectedLine(
                        False)  # switch off visibility of the control point for the line
                    self.selectedElement.updateAppearance()
                else:
                    self.selectedElement.update()

            # Update the currently selected icon
            self.selectedElement = item

        elif event.button() == Qt.MiddleButton or (event.button() == Qt.LeftButton and not self.itemAt(event.pos())):
            # if the user clicks on the canvas, deselect all icons and lines
            if self.selectedElement is not None:
                # If there is a previously selected line, reset its pen
                self.selectedElement.pen = QPen(Qt.black, 1)

                if isinstance(self.selectedElement, InteractiveLine):
                    self.selectedElement.setSelectedLine(
                        False)  # switch off visibility of the control point for the line
                    self.selectedElement.updateAppearance()
                elif isinstance(self.selectedElement, MovableIcon):
                    self.selectedElement.update()

                self.selectedElement = None  # Reset the currently selected icon

            # now activate the panning mode
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()

        super().mousePressEvent(event)

    def startLine(self, port, pos):
        """
        Start drawing a new line from the given port (function called in the IconPort class)
        :param port: IconPort object or TriangleIconPorts object
        :param pos: Position of the mouse click
        :return:
        """
        if port.occupied:
            # do not start a new line if the port is already connected
            return

        else:
            if port.icon_type == ProcessType.INPUT and port.portType == 'exit':
                # the input is not restricted to one stream, so the port is not occupied, multiple streams can leave the
                # port
                port.occupied = False

            elif (port.icon_type not in [ProcessType.DISTRIBUTOR, ProcessType.BOOLDISTRIBUTOR] and
                  port.portType == 'exit' and len(port.connectionLines) > 0):
                # the port of an icon that is not a split icon and is an exit port is now occupied only one
                # stream can leave. The extra if statement is to avoid the case where the line was deleted
                # and no longer exists
                port.occupied = True
                # stop the line drawing process with return statement
                return

            # Start drawing a new line from this port
            self.logger.debug("Start drawing a new line from the port")

            self.startPort = port
            self.startPoint = pos  # Always corresponds to the exit port
            self.currentLine = InteractiveLine(startPoint=pos, endPoint=pos, centralDataManager=self.centralDataManager,
                                               startPort=port)  # QGraphicsLineItem(QLineF(pos, pos))
            port.connectionLines.append(self.currentLine)
            self.scene.addItem(self.currentLine)

    def endLine(self, port, pos, loadingLinesFlag=False, curveInfo=None):
        """
        End drawing a new line from the given port (function called in the IconPort class)
        :param port: IconPort object or TriangleIconPorts object
        :param pos: Position of the mouse click
        :return:
        """
        # Do not start a new line if the startPort is not set, This signals an error has occurred
        if self.startPort is None:
            return

        if self.startPort.portType == port.portType:
            return # you can not connect exit ports to each other of entry port to each other

        # Do not end a new line in a port that is already occupied
        if port.occupied:
            return

        if (port.icon_type in [ProcessType.DISTRIBUTOR, ProcessType.BOOLDISTRIBUTOR] and
            port.portType == 'entry' and len(port.connectionLines) > 0):
            port.occupied = True
            # you can not connect multiple units to the input of a distribution block
            # stop the line drawing process with return statement
            return

        if (self.startPort.icon_type in [ProcessType.DISTRIBUTOR, ProcessType.BOOLDISTRIBUTOR] and
            port.icon_type in [ProcessType.DISTRIBUTOR, ProcessType.BOOLDISTRIBUTOR]):
            # do not connect two split icons with each other
            return

        if (port.icon_type in [ProcessType.DISTRIBUTOR, ProcessType.BOOLDISTRIBUTOR]
            and self.startPort.icon_type == ProcessType.INPUT):
            # you can not connect the input icon with a distributor Icon! Splits are done automatically if the in put is
            # connected to various unit processes
            return

        # need to keep track of how many lines are leaving the distributor untis
        if self.startPort.icon_type in [ProcessType.DISTRIBUTOR, ProcessType.BOOLDISTRIBUTOR] and not loadingLinesFlag:
            # get the dto of the sending unit
            unitDTOSending = self.centralDataManager.unitProcessData[self.startPort.iconID]
            curvatureLinesDistributor = unitDTOSending.curvatureLinesDistributor

            if not curvatureLinesDistributor.keys():
                unitDTOSending.curvatureLinesDistributor[1] = None
                unitDTOSending.distributorLineUnitMap[port.iconID] = 1
            else:
                distributorStreamNumber = max(curvatureLinesDistributor.keys()) + 1
                unitDTOSending.curvatureLinesDistributor[distributorStreamNumber] = None
                unitDTOSending.distributorLineUnitMap[port.iconID] = distributorStreamNumber

        # need to keep track of how many lines are leaving the Input untis
        if self.startPort.icon_type == ProcessType.INPUT and not loadingLinesFlag:
            unitDTOSending = self.centralDataManager.unitProcessData[self.startPort.iconID]
            curvatureLinesInput = unitDTOSending.curvatureLinesInput

            if not curvatureLinesInput.keys():
                unitDTOSending.curvatureLinesInput[1] = None
                unitDTOSending.inputLineUnitMap[port.iconID] = 1
            else:
                inputStreamNumber = max(curvatureLinesInput.keys()) + 1
                unitDTOSending.curvatureLinesInput[inputStreamNumber] = None
                unitDTOSending.inputLineUnitMap[port.iconID] = inputStreamNumber

        self.logger.debug("End drawing a new line from the port")

        self.endPort = port
        self.endPoint = pos  # allways corresponds to the entry port

        # Here you might want to validate if the startPort and endPort can be connected
        if self.currentLine and self.startPort != port:
            self.currentLine.endPoint = pos  # Update the end point
            self.currentLine.endPort = port  # Update the end port
            if curveInfo:
                # get the current stream number we're working on
                if self.startPort.icon_type in [ProcessType.DISTRIBUTOR, ProcessType.BOOLDISTRIBUTOR]:
                    # if the start port is a distributor, we need to get the stream number from the curvatureLinesDistributor
                    distributorDTO = self.centralDataManager.unitProcessData[self.startPort.iconID]
                    if self.endPort.iconID in distributorDTO.distributorLineUnitMap: # make sure the end port is in the map
                        streamNumber = distributorDTO.distributorLineUnitMap[self.endPort.iconID]
                        curveData = distributorDTO.curvatureLinesDistributor[streamNumber]
                    else:
                        curveData = []
                        self.logger.debug("Could not find curve data for the end "
                                          "port/distributor {}".format(self.endPort.iconID ))

                elif self.startPort.icon_type == ProcessType.INPUT:
                    # if the start port is an input, we need to get the stream number from the curvatureLinesInput
                    inputDTO = self.centralDataManager.unitProcessData[self.startPort.iconID]
                    if self.endPort.iconID in inputDTO.inputLineUnitMap:
                        streamNumber = inputDTO.inputLineUnitMap[self.endPort.iconID]
                        curveData = inputDTO.curvatureLinesInput[streamNumber]
                    else:
                        curveData = []
                        self.logger.debug("Could not find curve data for the end "
                                          "port/input {}".format(self.endPort.iconID))

                else:
                    streamNumber = self.startPort.exitStream
                    curveData = curveInfo[streamNumber]

                # set the control point ect using the _setCurveData Method
                self._setCurveData(curveData=curveData)
            self.currentLine.updateAppearance()  # Update the line appearance based on its current state
            port.connectionLines.append(self.currentLine)

            # manage logic of the connecting Icons here
            unitDTOSending = self.centralDataManager.unitProcessData[self.startPort.iconID]
            unitDTOReceiving = self.centralDataManager.unitProcessData[self.endPort.iconID]

            # if we are drawing lines from loaded data the dialog data is already loaded and established, so no need to
            # establish the connection again, this we'll only lead to duplication errors
            if not loadingLinesFlag:
                errorFlag = self._establishConnection(unitDTOSending, unitDTOReceiving)
                if errorFlag:
                    return

        # rest the positions and switches to None
        self.startPoint = None
        self.endPoint = None
        self.currentLine = None
        self.drawingLine = False

    def _getEndPort(self, iconWidget):
        """
        Get End/stop port of the connection
        :param icon:
        :param connection:
        :return:
        """
        for port in iconWidget.ports:
            if port.portType == 'entry':
                return port

    def _getStartPort(self, iconWidget, streamNumber):
        """
        Get start port of the connection
        :param icon:
        :param connection:
        :return:
        """
        for port in iconWidget.ports:
            if port.portType == 'exit' and port.exitStream == streamNumber:
                return port

    def _setCurveData(self, curveData):
        # only set if there is curve data, could be empty
        if curveData:
            x = curveData[0]
            y = curveData[1]
            self.currentLine.controlPoint = ControlPoint(x, y, self.currentLine)
            self.currentLine.isCurved = True
            self.currentLine.controlPoint.setVisible(False)
            self.currentLine.selected = False

    def loadInResults(self, selectedUnits, connectedUnits):
        """
        Import the data from the centralDataManager to the canvas. This method is called when the data is loaded from a
        file and an established central data Manager exists.
        The method creates the icons and connections between the icons based on the data in the centralDataManager.
        :return:
        """
        unitUIDs = list(selectedUnits.keys())
        if self.centralDataManager.unitProcessData:  # only if there is data in the centralDataManager
            # unitDTOs = self.centralDataManager.unitProcessData
            allMoveableIcons = {}

            # ---------------------------------------------------
            # Step 1: place all the icons on the canvas
            # ---------------------------------------------------
            for uid, name in selectedUnits.items():
                # get the dto of the unit
                unitDTO = self.centralDataManager.unitProcessData[uid]
                # create the icon widget based on the type of the unit
                iconWidget = MovableIcon(text=name, centralDataManager=self.centralDataManager,
                                         signalManager=self.signalManager, icon_type=unitDTO.type,
                                         position=unitDTO.positionOnCanvas,
                                         iconID=uid, initiatorFlag=False)

                position = unitDTO.positionOnCanvas
                # iconWidget.setPos(self.mapToScene(position))
                # Set the icon's position to the mouse cursor's position
                iconWidget.setPos(position)
                self.scene.addItem(iconWidget)  # Add the created icon to the scene

                # update the outlet port of the icon based on the dialog data
                if unitDTO.type.value in list(
                    range(1, 7)) and unitDTO.dialogData:  # not input and output are selected, only process types
                    stream2 = unitDTO.dialogData['Check box stream 2']
                    stream3 = unitDTO.dialogData['Check box stream 3']
                    activeStreamsList = [True, stream2, stream3]  # stream 1 is always active
                    # update the ports if other check boxes are active
                    iconWidget.updateIconExitPorts(activeStreamsList, unitDTO)
                # add the icon to the list for the connections to be made
                allMoveableIcons.update({uid: iconWidget})

            # ---------------------------------------------------
            # Step 2: connect the icons with lines, if they are connected
            # ---------------------------------------------------
            for iconId, IconWidget in allMoveableIcons.items():
                unitDTO = self.centralDataManager.unitProcessData[iconId]
                # self.logger.debug('the curve info is:  {}'.format(curveInfo))
                # get the material flow of the unitDTO
                materialFlow = unitDTO.materialFlow

                if unitDTO.type in [ProcessType.DISTRIBUTOR, ProcessType.BOOLDISTRIBUTOR]:
                    for port in IconWidget.ports:
                        if port.portType == 'entry' and unitDTO.distributionOwner:  # don't bother if it's not connected
                            # get the owner of the distributor
                            ownerID = unitDTO.distributionOwner[0]
                            ownerWidget = allMoveableIcons[ownerID]
                            streamNumber = unitDTO.distributionOwner[1]
                            startPort = self._getStartPort(ownerWidget, streamNumber)
                            endPort = port

                            # get reciveing dto
                            receivingDTO = self.centralDataManager.unitProcessData[ownerID]
                            curveInfo = receivingDTO.curvatureLines  # get the curvature data if any
                            self.startLine(startPort, startPort.scenePos())
                            self.endLine(endPort, endPort.scenePos(), loadingLinesFlag=True, curveInfo=curveInfo)

                        elif port.portType == 'exit' and unitDTO.distributionContainer:
                            # get the owner of the distributor
                            for receivingID in unitDTO.distributionContainer:
                                if receivingID not in unitUIDs:
                                    continue
                                receivingWidget = allMoveableIcons[receivingID]
                                startPort = port
                                endPort = self._getEndPort(receivingWidget)
                                self.startLine(startPort, startPort.scenePos())

                                if unitDTO.curvatureLinesDistributor:
                                    curveInfoDistributor = unitDTO.curvatureLinesDistributor
                                    self.endLine(endPort, endPort.scenePos(), loadingLinesFlag=True,
                                                 curveInfo=curveInfoDistributor)
                                else:
                                    self.logger.error(
                                        "No curvature data for the distributor found, using default straight line")
                                    curveInfo = {}
                                    self.endLine(endPort, endPort.scenePos(), loadingLinesFlag=True,
                                                 curveInfo=curveInfo)

                        else:
                            continue  # if the distributor is not connected, don't bother connecting it

                else:  # for the other icons that are not distributors
                    # loop through all the ports in the icon
                    curveInfo = unitDTO.curvatureLines
                    for port in IconWidget.ports:
                        # connect inputs
                        if port.portType == 'entry':
                            inputFlows = unitDTO.inputFlows
                            for sendingID in inputFlows:
                                sendingWidget = allMoveableIcons[sendingID]  # this should always be an input icon
                                # the first port is the only (exit) port in the input icon
                                startPort = sendingWidget.ports[0]
                                endPort = port  # the current port is the end port of the connection

                                # now retrieve the correct curvature info
                                self.startLine(startPort, startPort.scenePos())
                                inputDTO = self.centralDataManager.unitProcessData[sendingID]

                                if inputDTO.curvatureLinesInput:
                                    curveInfoInput = inputDTO.curvatureLinesInput
                                    self.endLine(endPort, endPort.scenePos(), loadingLinesFlag=True,
                                                 curveInfo=curveInfoInput)
                                else:
                                    self.logger.error("No curvature data for the distributor found, "
                                                      "using default straight line")
                                    curveInfo = {}
                                    self.endLine(endPort, endPort.scenePos(), loadingLinesFlag=True,
                                                 curveInfo=curveInfo)


                        # connect processes and outputs
                        else:  # exit ports
                            streamNumber = port.exitStream
                            classification = unitDTO.classificationStreams[streamNumber]
                            if classification is None:
                                targetIds = list(materialFlow[streamNumber].keys())
                                if targetIds:  # only connect if there is a target to connect to
                                    targetId = targetIds[0]
                                    targetWidget = allMoveableIcons[targetId]
                                    startPort = port  # the current port is the start port of the connection
                                    endPort = self._getEndPort(targetWidget)
                                    self.startLine(startPort, startPort.scenePos())
                                    self.endLine(endPort, endPort.scenePos(), loadingLinesFlag=True,
                                                 curveInfo=curveInfo)

                            elif classification == ProcessType.BOOLDISTRIBUTOR:
                                # first identify which units are connected to the bool distributor
                                targetIds = list(materialFlow[streamNumber].keys())
                                # get all combinations of the current unit uid and the potential target uids to find
                                # which matches with the keys of the dictionary connectedUnits containing the
                                # connections between the units
                                idTupleList = [(unitDTO.uid, i) for i in targetIds]
                                for idtuple in idTupleList:
                                    if idtuple in list(connectedUnits.keys()):
                                        targetId = idtuple[1]
                                        targetWidget = allMoveableIcons[targetId]
                                        startPort = port  # the current port is the start port of the connection
                                        endPort = self._getEndPort(targetWidget)
                                        self.startLine(startPort, startPort.scenePos())
                                        self.endLine(endPort, endPort.scenePos(), loadingLinesFlag=True,
                                                     curveInfo=curveInfo)




    def _warningCalculatingDialogbox(self):
        pass





