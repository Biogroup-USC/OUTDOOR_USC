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


class Canvas(QGraphicsView):
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
        self.importData()

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
        elif self.isPanning and self.lastPanPoint:
            # Calculate how much to move the view
            delta = event.pos() - self.lastPanPoint
            self.lastPanPoint = event.pos()

            # Move the scene by scrolling
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()

        else:
            # Not drawing a line, so pass the event to the base class
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.isPanning and (event.button() == Qt.MiddleButton or event.button() == Qt.LeftButton):
            self.isPanning = False
            self.lastPanPoint = None
            self.setCursor(Qt.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def startLine(self, port, pos):
        """
        Start drawing a new line from the given port (function called in the IconPort class)
        :param port: IconPort object or TriangleIconPorts object
        :param pos: Position of the mouse click
        :return:
        """
        if port.occupied:
            # todo add a word to the canvas that disappears to indicate that the port is already occupied
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

    def _establishConnection(self, unitDTOSending, unitDTOReceiving):
        """
        Establish a connection between two unit processes base on the type of icons. This method is called when the
        line is drawn from the startPort to the endPort. The method updates the material flow of the sending unit and
        the receiving unit based on the current dialog data and how the ports are connected.

        :param sendingDTO: ProcessDTO of the sending unit
        :param recievingDTO: ProcessDTO of the receiving unit
        :return:
        """
        sendingIconType = unitDTOSending.type
        receivingIconType = unitDTOReceiving.type

        if sendingIconType == ProcessType.INPUT:
            unitDTOReceiving.updateProcessDTO(field=UpdateField.INPUT_FLOW,
                                              value=unitDTOSending.uid)
            self.logger.debug("Input {} given to unit {}:".format(unitDTOSending.uid, unitDTOReceiving.uid))
            self.logger.debug("The inputs going into Unit {} are: {}".format(unitDTOReceiving.uid, unitDTOReceiving.inputFlows))

        elif (sendingIconType.value in [1, 2, 3, 4, 5, 6] and
              (receivingIconType == ProcessType.BOOLDISTRIBUTOR or receivingIconType == ProcessType.DISTRIBUTOR)):

            # the ID of the sending unit and the stream number affected
            updateValue = (self.startPort.iconID, self.startPort.exitStream, receivingIconType)
            distributionDTO = unitDTOReceiving  # to make it clear that the receiving unit is the boolean distributor
            distributionDTO.updateProcessDTO(field=UpdateField.DISTRIBUTION_OWNER, value=updateValue)

            # update the classification Dictionary defining if stream are connected to the distributors
            ownerDTO = unitDTOSending
            stream = self.startPort.exitStream
            distributionType = receivingIconType
            distributionID = distributionDTO.uid
            ownerDTO.updateProcessDTO(field=UpdateField.STREAM_CLASSIFICATION, value=(stream, distributionType,
                                                                                      distributionID))

            # update the connection if the boolean distributor contains units that are already connected to it
            if distributionDTO.distributionContainer:
                # update the owner of the boolean distributor with the ID of the receiving unit and the stream number
                for receivingID in distributionDTO.distributionContainer:
                    updateValue = (receivingID, self.startPort.exitStream)
                    ownerDTO.updateProcessDTO(field=UpdateField.DISTRIBUTION_CONNECTION, value=updateValue)
                    receivingDTO = self.centralDataManager.unitProcessData[receivingID]
                    errorFlag = receivingDTO.updateProcessDTO(field=UpdateField.INCOMING_UNIT_FLOWS,
                                                  value={ownerDTO.uid: self.startPort.exitStream})
                    if errorFlag:
                        self.logger.error(
                            f"Error Updating incoming unit flows for process {receivingDTO.name} but the Unit {ownerDTO.name} is already \n"
                            f"conected by another stream with a different boolean connector. ABORTING CONNECTION")
                        return errorFlag

                    else:
                        self.logger.debug("Incoming flow ids for the receiving unitDTO {} "
                                      "are: {}".format(receivingID, receivingDTO.incomingUnitFlows))


            self.logger.debug("Distribution Connection between {} and {} established".format(ownerDTO.uid,
                                                                                            self.endPort.iconID))
            self.logger.debug("The connections are: {}".format(ownerDTO.materialFlow))
            self.logger.debug("The stream classification is: {}".format(ownerDTO.classificationStreams))


        elif ((sendingIconType == ProcessType.BOOLDISTRIBUTOR or sendingIconType == ProcessType.DISTRIBUTOR)
              and receivingIconType.value in [1, 2, 3, 4, 5, 6, 7]):

            distributionDTO = unitDTOSending  # to make it clear that the sending unit is a boolean distributor
            distributionDTO.updateProcessDTO(field=UpdateField.DISTRIBUTION_CONTAINER, value=unitDTOReceiving.uid)
            # if the boolean distributor has an owner, update the owner with the ID of the receiving unit and the stream
            # number affected
            if distributionDTO.distributionOwner:
                # retrieve the owner of the boolean distributor
                ownerID = distributionDTO.distributionOwner[0]  # get the ID of the owner of the boolean distributor
                ownerStream = distributionDTO.distributionOwner[1]  # get the stream number affected by the boolean distributor
                # get the DTO of the owner of the boolean distributor
                ownerDTO = self.centralDataManager.unitProcessData[ownerID]
                # update the owner of the boolean distributor with the ID of the receiving unit and the stream number
                updateValue = (self.endPort.iconID, ownerStream)
                ownerDTO.updateProcessDTO(field=UpdateField.DISTRIBUTION_CONNECTION, value=updateValue)

                self.logger.debug("Distribution Connection between {} and {} established".format(ownerID,
                                                                                                self.endPort.iconID))
                self.logger.debug("The connections are: {}".format(ownerDTO.materialFlow))
                self.logger.debug("The stream classification is: {}".format(ownerDTO.classificationStreams))

                # update what is id is entering the receiving unit

                errorFlag = unitDTOReceiving.updateProcessDTO(field=UpdateField.INCOMING_UNIT_FLOWS,
                                                  value={ownerID: ownerStream})
                if errorFlag:
                    self.logger.error(
                        f"Error Updating incoming unit flows for process {unitDTOReceiving.name} but the Unit {ownerDTO.name} is already \n"
                        f"conected by another stream with a different boolean connector. ABORTING CONNECTION")
                    return errorFlag

                else:
                    self.logger.debug("Incoming unit Flow id {} given to the receiving "
                                     "UnitDTO {}".format(ownerID, unitDTOReceiving.uid))
                    self.logger.debug("Incoming flow ids for the receiving unitDTO "
                                      "are: ".format(unitDTOReceiving.incomingUnitFlows))


        else: # the sending and receiving unit are 2 normal unit processes that are connected
            # Update the material flow of the process based on the current dialog data and how the ports are connected
            unitDTOSending.updateProcessDTO(field=UpdateField.CONNECTION,
                                            value=(self.startPort, self.endPort))

            self.logger.debug("Connection between {} and {} established".format(self.startPort.iconID, self.endPort.iconID))
            self.logger.debug("The connections are: {}".format(unitDTOSending.materialFlow))
            self.logger.debug("The stream classification is: {}".format(unitDTOSending.classificationStreams))

            errorFlag = unitDTOReceiving.updateProcessDTO(field=UpdateField.INCOMING_UNIT_FLOWS,
                                              value={unitDTOSending.uid: self.startPort.exitStream})
            if errorFlag:
                self.logger.warning(
                    f"Error Updating incoming unit flows for process {unitDTOReceiving.name} but the Unit {unitDTOSending.name} is already \n"
                    f"conected by another stream with a different boolean connector. ABORTING CONNECTION")

            else:
                self.logger.debug("Incoming unit Flow id {} given to the receiving "
                                 "unitDTO {}".format(unitDTOSending.uid, unitDTOReceiving.uid))
                self.logger.debug("Incoming flow ids for the receiving unitDTO are: "
                                  "{}".format(unitDTOReceiving.incomingUnitFlows))

        return False # no errors occurred

    def getSeperationDict(self, processType:ProcessType, streamType, dialogData):
        """
        Get the separation dictionary for the stream that is being sent from the startPort
        :param startPort:
        :return: splitDict: dictionary with the separation fractions for each chemical of the specified the stream
        """
        # if the process is an input process, all the chemicals are sent to the stream
        if processType.value == 0: # input
            return {'all': 1}

        if dialogData == {}: # if the dialog data is empty, return an empty dictionary with the default values
            return {} # to be updated with the dialog data!

        # retrieve the unit process DTO from the centralDataManager that is sending the connection
        separationList = dialogData['Separation Fractions']

        if streamType == 1:
            streamKey = 'Stream 1'
        elif streamType == 2:
            streamKey = 'Stream 2'
        elif streamType == 3:
            streamKey = 'Stream 3'
        else:
            streamKey = ''
            self.logger.error("Stream type not recognized when connecting to the port")

        # get the specific separation dictionary for the stream
        splitDict = {splitDict['Component']: splitDict[streamKey] for splitDict in separationList}

        return splitDict

    def keyPressEvent(self, event):
        """
        This method is called when a key is pressed in the canvas. It is used to delete icons and lines when pressing
        the backspace key, or to cancel line drawing when pressing the escape key.
        :param event:
        :return:
        """
        # deleting elements from the canvas
        if event.key() == Qt.Key_Backspace:
            for item in self.scene.selectedItems():
                self.logger.debug("Removing Item: {}".format(item))
                if isinstance(item, MovableIcon):
                    # get the ID of the icon (to remove it from the centralDataManager)
                    iconID = item.iconID
                    # list to store the outer ports of the connected icons, that is the ports where the lines are
                    # connected that do not belong to the icon! (these need to be reset in the second for loop)
                    outerPorts = []
                    deletedLines = []
                    outputFlowsToUpdate = []  # the ID's of sending units that need to be updated
                    inputFlowsToUpdate = []  # the ID's of the receiving units that need to be updated

                    # loop over all the ports associated with the icon to find which input and output flows need to be
                    # updated
                    for port in item.ports:
                        #port.occupied = False
                        self.logger.debug("Before Port {} # connectionLines: {}".format(port, len(port.connectionLines)))
                        connectionLines = port.connectionLines
                        for line in connectionLines:
                            # if the start port is not the port that is being deleted it is an outer port
                            # not belonging to the icon
                            if line.startPort != port:
                                outerPorts.append(line.startPort)
                                outputFlowsToUpdate.append(line.startPort.iconID)

                            if line.endPort != port:
                                outerPorts.append(line.endPort)
                                inputFlowsToUpdate.append(line.endPort.iconID)

                            deletedLines.append(line)
                            # remove the line from the scene
                            self.scene.removeItem(line)
                            # update the occupancy of the port to False
                        port.occupied = False
                        port.connectionLines = []

                    # update the occupancy of the port to False for the ports that are not connected to the icon and are
                    # now free to connect to other icons
                    for port in outerPorts:
                        # update the occupancy of the port to False
                        port.occupied = False
                        for line in deletedLines:
                            if line in port.connectionLines:
                                port.connectionLines.remove(line)

                    # get the sending unit dto, extra if statement to avoid error if the icon is an input there is no
                    # sending unit, hence no need to remove the connection
                    self._removalLogic(outputFlowsToUpdate, inputFlowsToUpdate, item)

                    # remove the icon from the scene
                    self.scene.removeItem(item)
                    # remove the icon from the centralDataManager
                    self.centralDataManager.removeIconData(iconID)

        # Handle Escape key to cancel line drawing
        elif event.key() == Qt.Key_Escape:
            if self.currentLine is not None:
                # If currently drawing a line, cancel it
                self.logger.debug("Escape key pressed. Cancelling line drawing.")
                self.scene.removeItem(self.currentLine)

                # Reset the start and end points
                self.startPoint = None
                self.endPoint = None
                self.drawingLine = False

                # Reset the port occupancy
                self.startPort.connectionLines.remove(self.currentLine)
                self.startPort.occupied = False

                self.currentLine = None

        # Copy (Ctrl + C)
        elif event.matches(QKeySequence.Copy):
            self.copySelectedItems()
        # Paste (Ctrl + V)
        elif event.matches(QKeySequence.Paste):
            self.pasteSelectedItems()

        super().keyPressEvent(event)

    def copySelectedItems(self):
        """
        copies the selected items to the clipboard
        """
        item = self.selectedElement
        if isinstance(item, MovableIcon):
            self.logger.info("Copying selected Icon: {}".format(item.iconID))
            # get the dto info from the original icon
            self.dtoIconCopy = deepcopy(self.centralDataManager.unitProcessData[item.iconID])
            self.positionCopy = item.pos().toPoint()
            self.processTypeCopy = self.dtoIconCopy.type

    def pasteSelectedItems(self):
        """
        pastes the selected icon
        """
        self.logger.info("Pasting the copied Icon: ...")

        # get the current position of the old icon on the canvas
        position = self.positionCopy
        text = self.processTypeCopy

        # slightly off set the position so they don't overlap
        newPosX = position.x() + 4
        newPosY = position.y() + 4
        position = QPoint(newPosX, newPosY)
        #newPos = position.toPoint() #QPointF(newPosX, newPosY)

        icon = self.createMovableIcon(text=text, position=position, processType=text)
        if icon is None:
            self.logger.error("Could not paste the selected icon")
            return

        # Set the icon's position to the mouse cursor's position
        icon.setPos(position)
        self.scene.addItem(icon)  # Add the created icon to the scene

        # the only thing we want to copy to the new DTO is the Dialog data
        dtoCurrent = self.centralDataManager.unitProcessData[icon.iconID]
        dtoCurrent.addDialogData(self.dtoIconCopy.dialogData)

        # paint the new name of the copied process
        try:

            unitName = self.dtoIconCopy.name

            # Check if the end of the name is a number
            match = re.search(r"(\d+)$", unitName)
            if match:
                number = int(match.group(1))
                # Remove the original number from the end
                baseName = unitName[:match.start()]
                # Strip a trailing underscore if present
                baseName = baseName.rstrip("_")
                unitNameCopied = f"{baseName}_{number + 1}"
            else:
                # If there's no trailing number, start numbering at 1
                unitNameCopied = f"{unitName.rstrip('_')}_1"

        except:
            unitNameCopied = ''

        if unitNameCopied:
            dtoCurrent.name = unitNameCopied
            dtoCurrent.dialogData['Name'] = unitNameCopied
            icon.text = unitNameCopied  # Update the text attribute to reflect the new source name
            icon.update()  #

        # reset the copy variables to None
        self.positionCopy = None
        self.itemName = None
        self.dtoIconCopy = None

    def _removalLogic(self, outputFlowsToUpdate, inputFlowsToUpdate, icon2Delete):
        """
        This method is called when an icon is deleted. It updates the connections of the icons that are connected to the
        icon that is being deleted. The method removes the connection from the sending unitDTO to the receiving unitDTO

        :param outputFlowsToUpdate: list of ID's that surround (i.e. are connected to) the icon that is being deleted
        :param inputFlowsToUpdate: list of receiving Uint ID that need to be updated when an INPUT icon is deleted
        :param icon2Delete: the UID of the icon that is being deleted
        :return:
        """

        if icon2Delete.icon_type == ProcessType.INPUT:
            for id in inputFlowsToUpdate:
                unitDTOReceivingInput = self.centralDataManager.unitProcessData[id]
                unitDTOReceivingInput.inputFlows.remove(icon2Delete.iconID)
                self.logger.debug("Input {} removed from the receiving unitDTO {}".format(icon2Delete.iconID,
                                                                                         unitDTOReceivingInput.uid))
                self.logger.debug("Input flows for unit {} are: {}".format(unitDTOReceivingInput.uid, unitDTOReceivingInput.inputFlows))

                # get the name of the output
                inputName = self.centralDataManager.unitProcessData[icon2Delete.iconID].name
                # Get the current list, remove the item, and reassign it to trigger the signal
                current_list = self.signalManager.inputList
                # Safely remove the item if it exists
                if inputName in current_list:
                    current_list.remove(inputName)

                # Update the outputList to the centralDataManager
                # self.centralDataManager.inputList = current_list
                # This will emit the signal to update the output list for the dropdown menu in the GerenalSystemDataTab
                self.signalManager.inputList = current_list

        elif icon2Delete.icon_type == ProcessType.OUTPUT:
            outputID = icon2Delete.iconID
            # get the name of the output
            outputName = self.centralDataManager.unitProcessData[outputID].name

            # Get the current list, remove the item, and reassign it to trigger the signal
            current_list = self.signalManager.outputList
            # Safely remove the item if it exists
            if outputName in current_list:
                current_list.remove(outputName)

            # Update the outputList to the centralDataManager
            # self.centralDataManager.inputList = current_list
            # This will emit the signal to update the output list for the dropdown menu in the GerenalSystemDataTab
            self.signalManager.outputList = current_list

            # update the material flow of the owner of the output icon
            for id in outputFlowsToUpdate:
                unitDTOSending = self.centralDataManager.unitProcessData[id]
                unitDTOSending.removeFromMaterialFlow(outputID)
                self.logger.debug("Connection {} removed from the sending unitDTO".format(outputID))
                self.logger.debug("The amount of connections is: {}".format(len(unitDTOSending.materialFlow)))
                self.logger.debug("The connections are: {}".format(unitDTOSending.materialFlow))
                self.logger.debug("The classification streams are: {}".format(unitDTOSending.classificationStreams))

        elif icon2Delete.icon_type == ProcessType.DISTRIBUTOR or icon2Delete.icon_type == ProcessType.BOOLDISTRIBUTOR:
            # if you delete a split icon, you need to remove the connections to where the distribution goes from the
            # owner of the distribution ICON
            distrID = icon2Delete.iconID
            distributionDTO = self.centralDataManager.unitProcessData[distrID]
            id2Delete = distributionDTO.distributionContainer

            if distributionDTO.distributionOwner:  # if the distribution has an owner remove the connection to the owner
                ownerID = distributionDTO.distributionOwner[0]
                streamAffected = distributionDTO.distributionOwner[1]
                # it could be that the owner of the distribution icon is deleeted before the distribution icon
                # in that case the owner of the distribution icon is not in the centralDataManager anymore
                if ownerID not in self.centralDataManager.unitProcessData:
                    distributionDTO.distributionOwner = None
                    return

                ownerDTO = self.centralDataManager.unitProcessData[ownerID]
                # update the classification Dictionary defining where each individual stream goes
                ownerDTO.classificationStreams[streamAffected] = None
                ownerDTO.classificationId[streamAffected] = None
                for id in id2Delete:
                    ownerDTO.removeFromMaterialFlow(id)
                    if id in self.centralDataManager.unitProcessData: # could be already deleted, so check if it exists
                        receivingDTO = self.centralDataManager.unitProcessData[id]
                        receivingDTO.incomingUnitFlows.pop(ownerID)
                        self.logger.debug(
                            "Incoming flow ids for the receiving unitDTO are: {}".format(receivingDTO.incomingUnitFlows))

                self.logger.debug("Connections to the split icon removed\n"
                                 "The material flow of the owner of the split icon is updated to: "
                                 "{}".format(ownerDTO.materialFlow))
                self.logger.debug("The classification streams of the owner of the split icon is updated to: {}".format(
                    ownerDTO.classificationStreams))

        else: # any other process type
            for id in outputFlowsToUpdate:
                unitDTOSending = self.centralDataManager.unitProcessData[id]
                if unitDTOSending.type == ProcessType.DISTRIBUTOR or unitDTOSending.type == ProcessType.BOOLDISTRIBUTOR:
                    # if the sending unit is a distributor, the connection to the receiving unit needs to be removed
                    ownerID = unitDTOSending.distributionOwner[0]
                    if ownerID in self.centralDataManager.unitProcessData:  # could be already deleted, check if it exists
                        ownerDTO = self.centralDataManager.unitProcessData[ownerID]
                        ownerDTO.removeFromMaterialFlow(icon2Delete.iconID)

                        # log the changes
                        self.logger.debug("Connection {} removed from the sending unitDTO".format(ownerID))
                        self.logger.debug("The amount of connections is: {}".format(len(ownerDTO.materialFlow)))
                        self.logger.debug("The connections are: {}".format(ownerDTO.materialFlow))
                        self.logger.debug("The classification streams are: {}".format(ownerDTO.classificationStreams))

                    # we also have to remove the id of the icon we're deleting from the container of the distributor
                    unitDTOSending.distributionContainer.remove(icon2Delete.iconID)

                else:  # if the sending unit is not a distributor, the connection to the receiving unit needs to be removed
                    # remove the connection from the sending unitDTO (that is remove connection to current icon)
                    unitDTOSending.removeFromMaterialFlow(icon2Delete.iconID)  # remove the connection current Icon from the sending unitDTO
                    self.logger.debug("Connection {} removed from the sending unitDTO".format(self.endPort.iconID))
                    self.logger.debug("The amount of connections is: {}".format(len(unitDTOSending.materialFlow)))
                    self.logger.debug("The connections are: {}".format(unitDTOSending.materialFlow))
                    self.logger.debug("The classification streams are: {}".format(unitDTOSending.classificationStreams))

            for id in inputFlowsToUpdate:
                unitDTOReceiving = self.centralDataManager.unitProcessData[id]
                if unitDTOReceiving.type == ProcessType.DISTRIBUTOR or unitDTOReceiving.type == ProcessType.BOOLDISTRIBUTOR:
                    # if the unit is connected to a distributor, the distributor is no longer owned by any unit.
                    unitDTOReceiving.distributionOwner = None

                    # all the units that were previously linked to the deleted unit trough the distributor must be updated
                    if unitDTOReceiving.distributionContainer:
                        for id in unitDTOReceiving.distributionContainer:
                            unitConnectedToDistributor = self.centralDataManager.unitProcessData[id]
                            if icon2Delete.iconID in unitConnectedToDistributor.incomingUnitFlows:
                                unitConnectedToDistributor.incomingUnitFlows.pop(icon2Delete.iconID)


                    #pass
                    # unitDTOReceiving.distributionContainer.remove(icon2Delete.iconID)
                    # self.logger.debug("Connection {} removed from the distribution container".format(icon2Delete.iconID))
                else:
                    unitDTOReceiving.incomingUnitFlows.pop(icon2Delete.iconID)
                    self.logger.debug("Incoming Flow id {} removed from the receiving unitDTO".format(icon2Delete.iconID))
                    self.logger.debug("Incoming flow UIDs for unit {} are: {}".format(unitDTOReceiving.uid, unitDTOReceiving.inputFlows))

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
            self.isPanning = True
            self.lastPanPoint = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()

        # if it is just the empty space, deselect all icons and lines
        # else:  # if the selected element is an icon or a line, reset the pen
            # if self.selectedElement is not None:
            #     # If there is a previously selected line, reset its pen
            #     self.selectedElement.pen = QPen(Qt.black, 1)
            #
            #     if isinstance(self.selectedElement, InteractiveLine):
            #         self.selectedElement.setSelectedLine(
            #             False)  # switch off visibility of the control point for the line
            #         self.selectedElement.updateAppearance()
            #     elif isinstance(self.selectedElement, MovableIcon):
            #         self.selectedElement.update()
            #
            #     self.selectedElement = None  # Reset the currently selected icon

        super().mousePressEvent(event)

    def importData(self):
        """
        Import the data from the centralDataManager to the canvas. This method is called when the data is loaded from a
        file and an established central data Manager exists.
        The method creates the icons and connections between the icons based on the data in the centralDataManager.
        :return:
        """
        if self.centralDataManager.unitProcessData: # only if there is data in the centralDataManager
            unitDTOs = self.centralDataManager.unitProcessData
            allMoveableIcons = {}

            # ---------------------------------------------------
            # Step 1: place all the icons on the canvas
            # ---------------------------------------------------
            for uid, unitDTO in unitDTOs.items():
                if not unitDTO.name:
                    name = "Uncompleted Unit"
                else:
                    name = unitDTO.name

                iconWidget = MovableIcon(text=name, centralDataManager=self.centralDataManager,
                                   signalManager=self.signalManager, icon_type=unitDTO.type, position=unitDTO.positionOnCanvas,
                                   iconID=uid, initiatorFlag=False)

                position = unitDTO.positionOnCanvas
                # iconWidget.setPos(self.mapToScene(position))
                # Set the icon's position to the mouse cursor's position
                iconWidget.setPos(position)
                self.scene.addItem(iconWidget)  # Add the created icon to the scene

                # update the outlet port of the icon based on the dialog data
                if unitDTO.type.value in list(range(1, 7)) and unitDTO.dialogData:  # not input and output are selected, only process types
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
                        if port.portType == 'entry' and unitDTO.distributionOwner: # don't bother if it's not connected
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
                                receivingWidget = allMoveableIcons[receivingID]
                                startPort = port
                                endPort = self._getEndPort(receivingWidget)
                                self.startLine(startPort, startPort.scenePos())

                                if unitDTO.curvatureLinesDistributor:
                                    curveInfoDistributor = unitDTO.curvatureLinesDistributor
                                    self.endLine(endPort, endPort.scenePos(), loadingLinesFlag=True, curveInfo=curveInfoDistributor)
                                else:
                                    self.logger.error("No curvature data for the distributor found, using default straight line")
                                    curveInfo = {}
                                    self.endLine(endPort, endPort.scenePos(), loadingLinesFlag=True, curveInfo=curveInfo)

                        else:
                            continue # if the distributor is not connected, don't bother connecting it

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
                        else: # exit ports
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
                                    self.endLine(endPort, endPort.scenePos(), loadingLinesFlag=True, curveInfo=curveInfo)

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


class IconPort(QGraphicsEllipseItem):
    """
    A QGraphicsEllipseItem subclass to represent the entry and exit ports of the icons. This class handles the connection
    of lines between the ports.
    """

    def __init__(self, parent, portType, iconID, pos=None, exitStream=1):
        super().__init__(-5, -5, 10, 10, parent)  # A small circle

        # is it a port that receives or sends a stream
        self.portType = portType  # 'entry' or 'exit'

        # to identify the exiting stream that is connected to the port
        if portType == 'entry':
            self.exitStream = None # entry ports do not have an exit stream
        else:
            # exit ports have an exit stream that can be 1, 2, or 3 (depending on where the stram leaves)
            self.exitStream = exitStream
            # get the icon type
            iconType = parent.icon_type
            if iconType in [ProcessType.BOOLDISTRIBUTOR, ProcessType.DISTRIBUTOR]:
                self.distributorStreams = {}

        self.iconID = iconID
        self.setBrush(Qt.black)
        self.connectionLines = []  # List to store the lines connected to this iconPort
        self.occupied = False  # Flag to indicate if the port is already connected to a line
        self.icon_type = parent.icon_type

        if pos:
            self.setPos(pos)  # Set the position if it was passed (for split icons)
        else:
            # Position the port correctly on the parent icon based on portType
            match portType:
                case 'exit':
                    self.setPos(parent.boundingRect().width(), parent.boundingRect().height() / 2)
                case 'entry':
                    self.setPos(0, parent.boundingRect().height() / 2)

    def mousePressEvent(self, event):
        """
        Clicking on an exit port starts drawing a line from it
        """
        if event.button() == Qt.LeftButton and self.portType == 'exit':
            canvas = self.scene().views()[0]  # Get the first (and likely only) view
            if isinstance(canvas, Canvas):  # Check if it's actually your Canvas class
                canvas.startLine(self, event.scenePos())
        # return to parent class?
        # super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """
        The line is drawn from the exit port to the entry port
        """
        if self.portType == 'entry':
            canvas = self.scene().views()[0]  # Get the first (and likely only) view
            if isinstance(canvas, Canvas):  # Check if it's actually your Canvas class
                canvas.endLine(self, event.scenePos())

    def updateConnectedLines(self, centralDataManager):
        """
        Update the position of the lines connected to this port (function called in the Canvas class) when the port is
        moved. or that is when the icon is moved.
        :param centralDataManager:
        :return:
        """
        if self.connectionLines:
            # Loop through all lines connected to this port
            for line in self.connectionLines:
                # Update the position of the line's start or end, depending on the port's type
                if self.portType == "exit":
                    # If this is an exit port, update the line's start position
                    line.setStartPoint(self.scenePos())
                else:
                    # If this is an entry port, update the line's end position
                    line.setEndPoint(self.scenePos())

                # Redraw the line with its new position
                line.updateAppearance()


class MovableIcon(QGraphicsObject):
    """
    A QGraphicsObject subclass to represent the icons that can be dragged and dropped onto the canvas. This class also
    handles the ports of the icons. The icon type is used to determine the number and position of the ports. This class
    is used to create the icons in the canvas and makes them draggable, handels their appearance and opens dialogos.
    """

    def __init__(self, text, centralDataManager, signalManager, icon_type:ProcessType, position, iconID=None, initiatorFlag=True):
        """
        Initiate the moveable icon
        :param text: the text displayed on the icon
        :param centralDataManager:
        :param signalManager:
        :param icon_type: of the class
        :param position:
        :param iconID:
        :param initiatorFlag: Determines if a new dto object needs to be created
        """
        super().__init__()

        # set up the logger
        self.logger = logging.getLogger(__name__)
        # Set the text of the icon (the initial label)
        self.text = text
        # save the positon
        self.positionOnCanvas = position

        # make a map of abbreviations to full names of the icons
        self.iconAbbreviation = {ProcessType.INPUT: 'Input',
                                 ProcessType.OUTPUT: 'Output',
                                 ProcessType.PHYSICAL: 'Phy. Process',
                                 ProcessType.STOICHIOMETRIC: 'Stoich. Reactor',
                                 ProcessType.YIELD: 'Yield Reactor',
                                 ProcessType.GEN_ELEC: 'Generator',
                                 ProcessType.GEN_HEAT: 'Generator',
                                 ProcessType.BOOLDISTRIBUTOR: 'Bool Distr.',
                                 ProcessType.DISTRIBUTOR: 'Distr.',
                                 'LCA': 'LCA'}

        self.icon_type = icon_type
        self.iconID = iconID
        self.centralDataManager = centralDataManager  # to Store and handel dialog data for each icon
        self.signalManager = signalManager  # to handel the output data

        # save the initial icon to the centralDataManager
        if initiatorFlag:
            self.saveInitialIcon(icon_type)

        # set the flags for the icon to be movable and selectable
        self.setFlags(QGraphicsObject.ItemIsMovable)  # Enable the movable flag
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)  # Enable item change notifications
        self.setFlag(QGraphicsItem.ItemIsSelectable)  # Enable the selectable flag

        self.dragStartPosition = None

        # initiation of port logic
        self.activeStreams = [True, False, False] # stream 1 is always active

        self.pen = QPen(Qt.black, 1)  # Default pen for drawing the border
        #self.penBoarder = QPen(Qt.NoPen)
        # define the ports:
        self.ports = []
        match icon_type:
            case ProcessType.INPUT:
                exitPort = IconPort(self, portType='exit', iconID=iconID)
                self.ports.append(exitPort)
                #dto.exitPorts.append(exitPort)

            case ProcessType.OUTPUT:
                entryPort = IconPort(self, portType='entry', iconID=iconID)
                self.ports.append(entryPort)
                #dto.entryPorts.append(entryPort)

            case ProcessType.BOOLDISTRIBUTOR:
                self.addSplitPorts()

            case ProcessType.DISTRIBUTOR:
                self.addSplitPorts()

            # otherwise give port for entry and exit
            case _:
                exitPort = IconPort(self, portType='exit', iconID=iconID)
                self.ports.append(exitPort)
                #dto.exitPorts.append(exitPort)

                entryPort = IconPort(self, portType='entry', iconID=iconID)
                self.ports.append(entryPort)
                #dto.entryPorts.append(entryPort)


    def saveInitialIcon(self, unitType:ProcessType):
        """
        Creates an instance of the ProcessDTO and saves the data to the central data manager.
        The DTO is essentialy empty but will be filled with data from the dialogs.
        :return:
        """

        # else:
        #     self.logger.error("Icon type {} not recognized when saving the initial icon".format(unitType))
        #     self.logger.warning("Defaulting to physical process")
        #     type = ProcessType.PHYSICAL  # default to physical process if the type is not recognized


        # create a new processDTO and add the data to it the centralDataManager
        dtoProcess = ProcessDTO(uid=self.iconID, type=unitType, positionOnCanvas=self.positionOnCanvas)
        # add the processDTO to the centralDataManager
        self.centralDataManager.unitProcessData[self.iconID] = dtoProcess

        return dtoProcess

    def addSplitPorts(self):
        # Add an entry port
        entryPort = IconPort(self, portType='entry', iconID=self.iconID,
                             pos=QPointF(0, self.boundingRect().height() / 2))
        self.ports.append(entryPort)

        # Add exit ports
        exitPort = IconPort(self, pos=QPointF(self.boundingRect().width(), self.boundingRect().height() / 2),
                            portType='exit', iconID=self.iconID)
        self.ports.append(exitPort)

    def boundingRect(self):
        icon_type = self.icon_type
        if icon_type == ProcessType.BOOLDISTRIBUTOR or icon_type == ProcessType.DISTRIBUTOR:
            return QRectF(0, 0, 60, 60)
        else:
            return QRectF(0, 0, 120, 40)

    def paint(self, painter, option, widget=None):

        if self.icon_type == ProcessType.BOOLDISTRIBUTOR or self.icon_type == ProcessType.DISTRIBUTOR:
            # Set background color based on the icon type
            backgroundColor = QColor(self.getBackgroundColor(self.icon_type))
            painter.setBrush(backgroundColor)

            # Create a QPainterPath object
            path = QPainterPath()
            path.moveTo(0, 30)
            path.lineTo(60, 60)
            path.lineTo(60, 0)
            path.closeSubpath()

            # Draw the triangle
            painter.fillPath(path, painter.brush())
            painter.setPen(self.pen)
            painter.drawPath(path)

            # Set font and draw the letter B in the center of the triangle
            painter.setPen(Qt.black)  # Set pen color for the text
            font = QFont("Arial", 8, QFont.Bold)  # Set font size and weight
            painter.setFont(font)

            # Calculate the position for drawing the letter B in the middle
            text_rect = QRectF(0, 0, 60, 60)  # The bounding rectangle of the triangle
            if self.icon_type == ProcessType.DISTRIBUTOR:
                painter.drawText(text_rect, Qt.AlignCenter, "Distr.")
            else:
                painter.drawText(text_rect, Qt.AlignCenter, "Bool")


        else:
            # Set background color based on the icon type
            if self.text == "" or self.text == "Uncompleted Unit":
                # If no text is set, use a default color red, error needs to be filled in!!
                backgroundColor = QColor("#FF6347")  # tomato red

            else:
                backgroundColor = QColor(self.getBackgroundColor(self.icon_type))

            painter.setBrush(backgroundColor)
            painter.setPen(self.pen)
            painter.drawRoundedRect(self.boundingRect(), 10, 10)

            painter.setPen(Qt.black)
            font = QFont("Arial", 10)
            painter.setFont(font)

            # get the start name of the icon from the map
            iconText = self.iconAbbreviation.get(self.text, self.text)
            painter.drawText(self.boundingRect(), Qt.AlignCenter, iconText)

    def getBackgroundColor(self, icon_type):
        if icon_type == ProcessType.INPUT:
            return "#a8d5e2"  # pastel blue (a bit darker than the original)

        elif icon_type == ProcessType.OUTPUT:
            return "#ffdab9"  # pastel peach (more distinct from orange)

        elif icon_type == ProcessType.PHYSICAL:
            return "#f7c6d9"  # pastel pink (distinct from the other colors)

        elif icon_type == ProcessType.STOICHIOMETRIC:
            return "#c8e6c9"  # pastel green (slightly different)

        elif icon_type == ProcessType.YIELD:
            return "#d4b3ff"  # pastel lavender (more distinguishable from pink)

        elif icon_type == ProcessType.GEN_ELEC:
            return "#fff4a3"  # pastel yellow (brighter but still soft)

        elif icon_type == ProcessType.GEN_HEAT:
            return "#ffb3b3"  # pastel yellow (more vibrant but still light)

        # elif icon_type == 'generator':
        #     return "#fff4a3"  # pastel yellow (brighter but still soft)

        elif icon_type == ProcessType.BOOLDISTRIBUTOR:
            return "#ffd1dc"  # pastel rose (different from light red)

        elif icon_type == ProcessType.DISTRIBUTOR:
            return "#b2f2bb"  # pastel mint green (to distinguish from green)

        # if none of the above, return a gray color
        return "#D3D3D3"

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Change the pen color to indicate the icon is selected black
            self.pen = QPen(QColor("red"), 2)  # 3 is the width of the pen
            self.update()  # Update the icon's appearance
            self.setCursor(Qt.ClosedHandCursor)
            self.dragStartPosition = event.pos()

        super().mousePressEvent(event)  # Ensure the event is propagated

    def mouseMoveEvent(self, event):
        if not self.dragStartPosition:
            return
        dragDistance = (event.pos() - self.dragStartPosition).manhattanLength()
        if dragDistance >= QApplication.startDragDistance():
            # Calculate the new position
            newPos = event.scenePos() - self.dragStartPosition
            self.setPos(newPos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.logger.debug("Icon {} released. Current position: {}".format(self.iconID, self.pos()))
        # update the position of the icon in the centralDataManager
        self.centralDataManager.unitProcessData[self.iconID].positionOnCanvas = self.pos()
        # get the scene items
        sceneItems = self.scene().items()
        self.logger.debug("Scene items: {}".format(len(sceneItems)))
        self.setCursor(Qt.OpenHandCursor)
        self.dragStartPosition = None
        super().mouseReleaseEvent(event)  # Ensure the event is propagated

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.icon_type == ProcessType.BOOLDISTRIBUTOR or self.icon_type == ProcessType.DISTRIBUTOR:
                # self.openSplittingDialog()
                pass
            else:
                self.openParametersDialog()

    # methods to manage the positions of lines between the icons
    def itemChange(self, change, value):
        if change == QGraphicsObject.ItemPositionHasChanged:
            for port in self.childItems():
                if hasattr(port, 'updateConnectedLines'):
                    port.updateConnectedLines(self.centralDataManager)
        return super().itemChange(change, value)

    def openParametersDialog(self):
        """
        Handles the data entered by the user after pressing OK for the icon parameters dialog
        :return:
        """

        # Retrieve existing data for this icon
        existingData = self.centralDataManager.unitProcessData.get(self.iconID,
                                                        {})  # if the iconID is not in the dict, return an empty dict

        # choose the dialog to open based on the type of icon that was double clicked
        if self.icon_type == ProcessType.INPUT:
            dialog = InputParametersDialog(initialData=existingData, centralDataManager=self.centralDataManager,
                                           signalManager= self.signalManager, iconID=self.iconID)

        elif self.icon_type == ProcessType.OUTPUT:
            dialog = OutputParametersDialog(initialData=existingData, centralDataManager=self.centralDataManager,
                                            signalManager=self.signalManager, iconID=self.iconID)

        elif self.icon_type == ProcessType.PHYSICAL:
            dialog = PhysicalProcessesDialog(initialData=existingData, centralDataManager=self.centralDataManager, iconID=self.iconID)

        elif self.icon_type == ProcessType.STOICHIOMETRIC:
            dialog = StoichiometricReactorDialog(initialData=existingData, centralDataManager=self.centralDataManager, iconID=self.iconID)

        elif self.icon_type == ProcessType.YIELD:
            dialog = YieldReactorDialog(initialData=existingData, centralDataManager=self.centralDataManager,
                                        iconID=self.iconID)

        elif self.icon_type == ProcessType.GEN_ELEC or self.icon_type == ProcessType.GEN_HEAT or self.icon_type == ProcessType.GEN_CHP:
             dialog = GeneratorDialog(initialData=existingData, centralDataManager=self.centralDataManager,
                                      iconID=self.iconID)

        elif self.icon_type == ProcessType.LCA:
            dialog = LCADialog(initialData=existingData, centralDataManager=self.centralDataManager)

        else:
            self.logger.error("Icon type {} not recognized".format(self.icon_type))  # You can handle this error in a more user-friendly way


        #  open the dialog and handle the data entered by the user after pressing OK
        # Basically updates the centralDataManager and the appearance of the icon
        # -------------------------------------------------------------------------------------------------------------

        if dialog.exec_():
            unitDTO = self.centralDataManager.unitProcessData[self.iconID]

            try:
                newSourceName = unitDTO.name
            except:
                newSourceName = ''

            if newSourceName:
                self.text = newSourceName  # Update the text attribute to reflect the new source name
                self.update()  # Update the icon's appearance i.e., repaint the icon name

            # update the outlet port of the icon based on the dialog data
            if unitDTO.type.value != 0 and unitDTO.type.value != 7:  # not input and output are selected
                stream2 = unitDTO.dialogData['Check box stream 2']
                stream3 = unitDTO.dialogData['Check box stream 3']
                activeStreamsList = [True, stream2, stream3]  # stream 1 is always active
                self.updateIconExitPorts(activeStreamsList, unitDTO)

            # update the material flow of the leaving streams that are changed
            unitDTO.updateProcessDTO(field=UpdateField.MATERIALFLOW, value=None)


            self.logger.debug("{} Dialog accepted".format(self.icon_type))
        else:
            self.logger.debug("{} Dialog canceled".format(self.icon_type))

    def updateIconExitPorts(self, ports2Active:list, processDTO:ProcessDTO):
        """
        Updates the exit ports of the icon based on the provided list of active ports.
        Adds or removes exit ports as needed.
        :param ports2Active: A list with boolean values indicating if each stream (port) should be active.
        """
        # Calculate the new step size
        heightIcon = self.boundingRect().height()
        widthIcon = self.boundingRect().width()

        # Loop through the ports2Active list and compare it with self.activeStreams
        for index, shouldBeActive in enumerate(ports2Active):
            # If the port should be active but is not currently active, add it
            if shouldBeActive and not self.activeStreams[index]:
                # Calculate the position for the new port
                if index == 1:
                    # Port 2 (upper port)
                    x = widthIcon / 2
                    y = 0

                elif index == 2:
                    # Port 3 (lower port)
                    x = widthIcon / 2
                    y = heightIcon
                else:
                    continue  # Stream 1 is always active and has already been added

                # Create and add the new port
                newPort = IconPort(self, pos=QPointF(x, y), portType='exit', iconID=self.iconID, exitStream=index+1) # beacuse the index starts at 0
                self.ports.append(newPort)
                processDTO.exitPorts.append(newPort)
                self.activeStreams[index] = True

            # If the port should not be active but is currently active, remove it
            elif not shouldBeActive and self.activeStreams[index]:
                # Find and remove the corresponding port
                for port in self.ports:
                    if isinstance(port, IconPort) and port.portType == 'exit':
                        portPos = port.pos()
                        if ((index == 1 and portPos == QPointF(widthIcon / 2, 0)) or
                            (index == 2 and portPos == QPointF(widthIcon / 2, heightIcon))):
                            # Remove the port from the scene
                            self.scene().removeItem(port)
                            self.ports.remove(port)
                            processDTO.exitPorts.remove(port)
                            del port
                            break

                # Update activeStreams list
                self.activeStreams[index] = False

        # Update the icon after modifications
        self.update()


class ControlPoint(QGraphicsEllipseItem):
    """
    A QGraphicsEllipseItem subclass to represent the control point for curved lines. This class is used to create the
    control points when a line is curved and allows the user to adjust the curve by moving the control point.
    """

    def __init__(self, x, y, parent=None):
        super().__init__(-5, -5, 10, 10, parent)  # A small circle as the control point
        self.setBrush(QColor(255, 0, 0))  # Red color
        self.setFlag(QGraphicsEllipseItem.ItemIsMovable)
        self.setFlag(QGraphicsEllipseItem.ItemSendsGeometryChanges)
        self.setFlag(QGraphicsItem.ItemIsFocusable)  # Enable focus

        self.setPos(x, y)  # Set initial position

    def itemChange(self, change, value):
        if change == QGraphicsEllipseItem.ItemPositionHasChanged and self.parentItem():
            self.parentItem().updateAppearance()  # Update the line's appearance when the control point is moved, the methode is in the InteractiveLine class (the parent)
        return super().itemChange(change, value)


class InteractiveLine(QGraphicsPathItem):
    """
    This class is used to create the lines between the icons. It allows the user to draw straight or curved lines by
    double-clicking on the line to toggle between the two modes. The control point for curved lines is only shown when
    the line is curved and selected.
    """

    def __init__(self, startPoint, endPoint, centralDataManager, startPort=None, endPort=None, parent=None):
        super().__init__(parent)

        # initiate the logger
        self.logger = logging.getLogger(__name__)

        # add the centralDataManager
        self.centralDataManager = centralDataManager

        self.startPoint = startPoint
        self.endPoint = endPoint
        self.isCurved = False  # Line starts as straight
        self.controlPoint = None  # Control point is not created until needed
        self.startPort = startPort
        self.endPort = endPort

        # set Flags
        # self.setAcceptHoverEvents(True)  # Enable hover events
        # self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemIsFocusable)  # Enable focus

        self.selected = True  # Track selection state
        self.pen = QPen(Qt.black, 1)  # Default pen for drawing the line
        self.updateAppearance()

    def setStartPoint(self, point):
        self.startPoint = point
        self.updateAppearance()

    def setEndPoint(self, point):
        self.endPoint = point
        self.updateAppearance()

    def mousePressEvent(self, event):


        if event.button() == Qt.LeftButton:
            # The user clicked on the line
            self.setSelectedLine(not self.selected)  # Select the line

            if self.selected:
                self.pen = QPen(Qt.red, 1.5)  # Increase line thickness
                # print('lines have been clicked and selected')
            else:
                self.pen = QPen(Qt.black, 1)

            self.updateAppearance()  # Update appearance

        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.isCurved = not self.isCurved  # Toggle between curved and straight line
        if self.isCurved and not self.controlPoint:
            # Create and add the control point only if transitioning to curved for the first time
            midPoint = QPointF((self.startPoint.x() + self.endPoint.x()) / 2,
                               (self.startPoint.y() + self.endPoint.y()) / 2)
            self.controlPoint = ControlPoint(midPoint.x(), midPoint.y(), self)

        else: # deactivate the line curve data if it's not active any more
            # get the DTO from where the line starts from and the stream number
            streamNumber = self.startPort.exitStream
            idDTO = self.startPort.iconID
            sendingDTO = self.centralDataManager.unitProcessData[idDTO]
            if sendingDTO.type in [ProcessType.DISTRIBUTOR, ProcessType.BOOLDISTRIBUTOR]:
                nr = sendingDTO.distributorLineUnitMap[self.endPort.iconID]
                sendingDTO.curvatureLinesDistributor[nr] = None

            elif sendingDTO.type == ProcessType.INPUT:
                nr = sendingDTO.inputLineUnitMap[self.endPort.iconID]
                sendingDTO.curvatureLinesInput[nr] = None

            else:
                sendingDTO.curvatureLines[streamNumber] = None

        self.updateAppearance()
        super().mouseDoubleClickEvent(event)

    def setSelectedLine(self, selected):
        self.selected = selected
        if self.isCurved and self.controlPoint:
            self.controlPoint.setVisible(self.selected)
        elif not self.isCurved and self.controlPoint:
            self.controlPoint.setVisible(False)

    def keyPressEvent(self, event):
        # terminate drawing is in the canvas class, this is to delete established lines
        if (event.key() == Qt.Key_Backspace or event.key() == Qt.Key_Delete) and self.selected:
            self.logger.debug("Delete key pressed. Deleting line with start port {} and end port {}".format(
                self.startPort.iconID, self.endPort.iconID if self.endPort else "None"
            ))

            # reset the occupied flag of the start and end port
            self.startPort.occupied = False
            # delete the line from the connectionLines list of the ports
            self.startPort.connectionLines.remove(self)

            # there is no end port if you have not connected the line,
            # so no need to remove it or update the material flow
            if self.endPort:
                self.endPort.occupied = False
                self.endPort.connectionLines.remove(self)

                # update the material flow of the affected units
                self._lineDeletingLogic()

            # Delete the line if the Backspace key is pressed while the line is selected
            self.setSelectedLine(False)
            #self.logger.debug("The scene is: {}".format(self.scene()))
            self._findFoucs("The focus BEFORE deleting the line")
            print('')
            self.logger.debug("Scene items before deletion: {}".format(len(self.scene().items())))
            self.scene().removeItem(self)

            # revisit this part of the code
            try:
                sceneItems = self.scene().items()
            except:
                sceneItems =None

            self.logger.debug("Scene items after deletion: {}".format(sceneItems))
            # it's strange no items are found in the scene after deleting the line...

            #self.logger.debug("The scene after deleting is: {}".format(self.scene()))
            #self._findFoucs("The focus AFTER deleting the line")


        super().keyPressEvent(event)

    def _lineDeletingLogic(self):
        """
        Handles the removal of the line from the material flow of the affected units
        :param startPort: The port where the line starts
        :param endPort: The port where the line ends
        :return:
        """

        # get the sending receiving unit dto's
        unitDTOSending = self.centralDataManager.unitProcessData[self.startPort.iconID]
        unitDTOReceiving = self.centralDataManager.unitProcessData[self.endPort.iconID]

        if unitDTOSending.type == ProcessType.INPUT:
            # update the input flow of the receiving unit
            unitDTOReceiving.inputFlows.remove(self.startPort.iconID)
            self.logger.debug("Input {} removed from the receiving unitDTO {}".format(unitDTOSending.uid,
                                                                                     unitDTOReceiving.uid))
            self.logger.debug("Input flows for unit {} are: {}".format(unitDTOReceiving.uid,
                                                                       unitDTOReceiving.inputFlows))

            # modify the input line map of the sending unit to get the curvature correctly
            id2Delete = unitDTOReceiving.uid
            inputLineNumber = unitDTOSending.inputLineUnitMap.get(id2Delete, None)
            # delete the curvature line from the distributor dictionary
            unitDTOSending.curvatureLinesInput.pop(inputLineNumber, None)
            unitDTOSending.inputLineUnitMap.pop(id2Delete, None)


        elif (unitDTOSending.type.value in [1, 2, 3, 4, 5, 6] and
              (unitDTOReceiving.type == ProcessType.DISTRIBUTOR or unitDTOReceiving.type == ProcessType.BOOLDISTRIBUTOR)):

            # if the receiving unit is a distributor, the connection to the sending unit needs to be removed
            ownerID = unitDTOReceiving.distributionOwner[0]
            ownerDTO = self.centralDataManager.unitProcessData[ownerID]
            ids2Delete = unitDTOReceiving.distributionContainer # unitDTOReceiving if of the type distributor

            # update the classification Dictionary defining where each individual stream goes
            streamAffected = unitDTOReceiving.distributionOwner[1]
            ownerDTO.classificationStreams[streamAffected] = None
            ownerDTO.classificationId[streamAffected] = None

            # delete the connection from the unit that owned the distribution unit
            for id in ids2Delete:
                ownerDTO.removeFromMaterialFlow(id)
                receivingDTO = self.centralDataManager.unitProcessData[id]
                receivingDTO.incomingUnitFlows.pop(ownerID)  # remove the incoming flow from the receiving units
                self.logger.debug("Incoming flow ids for the receiving unitDTO are: {}".format(receivingDTO.incomingUnitFlows))

            # reset the ownership of the distribution unit
            unitDTOReceiving.distributionOwner = None

            self.logger.debug("Connection {} removed from the sending unitDTO".format(ownerID))
            self.logger.debug("The connections are: {}".format(ownerDTO.materialFlow))
            self.logger.debug("The classification of streams are: {}".format(ownerDTO.classificationStreams))

        elif ((unitDTOSending.type == ProcessType.DISTRIBUTOR or unitDTOSending.type == ProcessType.BOOLDISTRIBUTOR)
              and unitDTOReceiving.type.value in [1, 2, 3, 4, 5, 6, 7]):

            id2Delete = unitDTOReceiving.uid
            unitDTOSending.distributionContainer.remove(id2Delete)

            distributorLineNumber = unitDTOSending.distributorLineUnitMap.get(id2Delete, None)
            # delete the curvature line from the distributor dictionary
            unitDTOSending.curvatureLinesDistributor.pop(distributorLineNumber, None)
            unitDTOSending.distributorLineUnitMap.pop(id2Delete,None)

            if unitDTOSending.distributionOwner:
                ownerID = unitDTOSending.distributionOwner[0]
                ownerDTO = self.centralDataManager.unitProcessData[ownerID]
                ownerDTO.removeFromMaterialFlow(id2Delete)
                self.logger.debug("Connection {} removed from the sending unitDTO".format(ownerID))
                self.logger.debug("The connections are: {}".format(ownerDTO.materialFlow))
                self.logger.debug("The classification of streams are: {}".format(ownerDTO.classificationStreams))

                # update the incoming flow of the receiving unit
                unitDTOReceiving.incomingUnitFlows.pop(ownerID, None)
                self.logger.debug("Incoming flow ids for the receiving unitDTO {} are:"
                                  " {}".format(ownerID, unitDTOReceiving.incomingUnitFlows))

        # just a normal connection between two units that are not distributors
        else:
            # remove the connection from the sending unitDTO
            # remove the connection from the receiving unitDTO
            unitDTOSending.removeFromMaterialFlow(self.endPort.iconID)
            self.logger.debug("Connection {} removed from the sending unitDTO".format(self.endPort.iconID))
            self.logger.debug("The connections are: {}".format(unitDTOSending.materialFlow))
            self.logger.debug("The classification of streams are: {}".format(unitDTOSending.classificationStreams))

            # remove the incoming flow from the receiving unit, returns None if the key is not found. Necessary to avoid
            # KeyError when the line is deleted from a distributor to which a unit is connected to
            unitDTOReceiving.incomingUnitFlows.pop(self.startPort.iconID, None)
            self.logger.debug("Incoming flow id {} removed from the receiving "
                              "unitDTO {}".format(self.startPort.iconID, unitDTOReceiving.uid))


    def _findFoucs(self, text):
        focused_widget = QApplication.focusWidget()
        if focused_widget:
            self.logger.debug("{}: {}".format(text, focused_widget))
        else:
            self.logger.debug("No widget currently has focus.")

    def updateAppearance(self):
        path = QPainterPath(self.startPoint)
        if self.isCurved and self.controlPoint:
            # Use the control point's current position for the curve
            controlPos = self.controlPoint.pos()
            path.quadTo(controlPos, self.endPoint)

            # update the position of the control point
            # get the DTO from where the line starts from and the stream number
            streamNumber = self.startPort.exitStream
            idDTO = self.startPort.iconID
            sendingDTO = self.centralDataManager.unitProcessData[idDTO]
            receivingID = self.endPort.iconID

            if sendingDTO.type in [ProcessType.BOOLDISTRIBUTOR, ProcessType.DISTRIBUTOR]:
                # retrieve the correct number of curvature lines
                if receivingID in sendingDTO.distributorLineUnitMap:
                    # when deleting the line the curve data is removed and does not exist anymore, so check if it exists
                    distributorStreamNumber = sendingDTO.distributorLineUnitMap[receivingID]
                    sendingDTO.curvatureLinesDistributor[distributorStreamNumber] = (controlPos.x(), controlPos.y())

            elif sendingDTO.type == ProcessType.INPUT:
                # retrieve the correct number of curvature lines
                if receivingID in sendingDTO.inputLineUnitMap:
                    # when deleting the line the curve data is removed and does not exist anymore, so check if it exists
                    inputStreamNumber = sendingDTO.inputLineUnitMap[receivingID]
                    sendingDTO.curvatureLinesInput[inputStreamNumber] = (controlPos.x(), controlPos.y())
            else:
                sendingDTO.curvatureLines[streamNumber] = (controlPos.x(), controlPos.y())
            # self.logger.debug("control pos updated")

        else: # make a straight line
            path.lineTo(self.endPoint)

        self.setPath(path)
        self.setPen(self.pen)

    def shape(self):
        # Override shape method to return a wider hitbox
        stroker = QPainterPathStroker()
        stroker.setWidth(10)  # Set the hitbox width to be larger than the line width
        return stroker.createStroke(self.path())

    # def hoverEnterEvent(self, event):
    #     # Show the control point when hovering, but only if the line is curved
    #     if self.isCurved and self.controlPoint:
    #         self.controlPoint.setVisible(True)

    # def hoverLeaveEvent(self, event):
    #     # Hide the control point when not hovering
    #     if self.controlPoint:
    #         self.controlPoint.setVisible(False)

