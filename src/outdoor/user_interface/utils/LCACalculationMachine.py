import logging
import os
import sys
import uuid
from types import TracebackType

from PyQt5.QtWidgets import QLabel, QDialog, QVBoxLayout, QApplication
from PyQt5.QtGui import QMovie
from PyQt5.QtCore import Qt, QSize, QTimer

from outdoor.user_interface.utils.LCAWorker import LCAWorker

import bw2calc
import bw2calc as bc
import bw2data
import bw2data as bw
import pandas as pd

from outdoor.user_interface.data.CentralDataManager import CentralDataManager
from outdoor.user_interface.data.OutdoorDTO import OutdoorDTO
from outdoor.user_interface.dialogs.LcaButton import LcaButton


class LCACalculationMachine:

    def __init__(self, centralDataManager):
        self.logger = logging.getLogger(__name__)
        self.centralDataManager = centralDataManager
        self.methodSelectionLCA = self.centralDataManager.methodSelectionLCA

        if not centralDataManager:
            self.logger.error("CentralDataManager is not set. Please initialize it before using LCACalculationMachine.")
            return

        self.possibleLCAs = {
            "components":False,
            "waste":False,
            "utilities":False,
        }

        bwProjectNames = []
        for project in bw.projects:
            projectName = project.name
            bwProjectNames.append(projectName)

        if not bwProjectNames:
            self.logger.error("No Brightway projects found. Please Install the databases properly.")
            # close the calculation machine
            return

        projectName = self.centralDataManager.bdProjectName
        bw.projects.set_current(projectName)
        self.eidb = bw.Database(self.centralDataManager.technosphereDatabaseLCA)
        self.bios = bw.Database(self.centralDataManager.biosphereDatabaseLCA)
        # check the size of the databases
        if len(self.eidb) < 1 and len(self.bios) < 1:
            self.logger.warning("No databases found in project '{}'".format(projectName))
            self.logger.error("please check if you have correctly installed ecoinvent databases.")
            return

        self.outd = bw.Database('outdoor')

    def calculateAllLCAs(self, write=False):
        """
        This method runs through every set of OutdoorDTOs and checks if they can have MLCAs run on them.
        Shows a spinning wheel animation during calculations.
        """
        # Create a custom dialog with spinning wheel
        spinner_dialog = QDialog()
        spinner_dialog.setWindowTitle("LCA Calculation")
        spinner_dialog.setWindowFlags(spinner_dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint & ~Qt.WindowCloseButtonHint)
        spinner_dialog.setFixedSize(300, 150)

        # Create layout
        layout = QVBoxLayout(spinner_dialog)

        # Create label for the spinner
        spinner_label = QLabel()
        spinner_label.setAlignment(Qt.AlignCenter)

        # Create label for the text
        text_label = QLabel("Calculating LCAs. Please be patient, this may take a while...")
        text_label.setAlignment(Qt.AlignCenter)
        text_label.setWordWrap(True)

        # Add loading spinner animation
        gifPath = os.path.join(os.path.dirname(__file__), "loading.gif")
        movie = QMovie(gifPath)
        # If you don't have a GIF, you can use one from PyQt resources
        # or specify a full path like "C:/path/to/spinner.gif"
        movie.setScaledSize(QSize(50, 50))
        spinner_label.setMovie(movie)
        movie.start()

        # Add widgets to layout
        layout.addWidget(spinner_label)
        layout.addWidget(text_label)

        # Show the dialog
        spinner_dialog.show()
        QApplication.processEvents()

        try:
            # Do calculations
            self.logger.info("Collecting calculation-ready DTOs...")
            biglist = self.centralDataManager.componentData + self.centralDataManager.wasteData + self.centralDataManager.utilityData
            inventory = []
            incomplete = {}
            incomplete_count = 0

            # Rest of your calculation code...
            for component in biglist:
                component.LCA['Results'] = {}
                if len(component.LCA['exchanges']) > 0:
                    try:
                        inventory.append({self.outd.get(component.uid): 1})
                        self.logger.debug(f"Component {component.uid} has exchanges:{component.LCA['exchanges']}")
                    except Exception as e:
                        self.logger.warning(f"Looks like component {component.name} hasn't been saved to BW yet.")
                        incomplete_count += 1
                        if component.__class__.__name__ in incomplete:
                            incomplete[component.__class__.__name__].append(component.name)
                        else:
                            incomplete[component.__class__.__name__] = [component.name]
                else:
                    incomplete_count += 1
                    if component.__class__.__name__ in incomplete:
                        incomplete[component.__class__.__name__].append(component.name)
                    else:
                        incomplete[component.__class__.__name__] = [component.name]

            # Update status text
            text_label.setText(f"Found {len(inventory)} DTOs ready for calculation. Processing...")
            QApplication.processEvents()

            self.logger.info(f"Identified {len(inventory)} DTOs ready for calculation")
            self.logger.warning(f"There are {len(incomplete)} DTOs that are not ready for calculation: {incomplete}")
            self.logger.info(f"Beginning calculations. This may take a while.")

            # Continue with calculations
            execution = uuid.uuid4().__str__()
            methodconfs = self.getImpactMethods()
            calc_setup = {"inv": inventory, "ia": methodconfs}
            bw.calculation_setups[execution] = calc_setup

            text_label.setText("Please wait, calculating environmental impacts of each component \n ...")
            QApplication.processEvents()

            mlca = bw2calc.MultiLCA(execution)

            indic = []
            for f in mlca.func_units:
                for k in f:
                    indic.append(k['code'])
            cols = []
            for c in mlca.methods:
                cols.append(c[3])

            results = pd.DataFrame(mlca.results, columns=cols, index=indic).transpose().to_dict()

            text_label.setText("Processing results...")
            QApplication.processEvents()

            for k, v in results.items():
                self.logger.debug(f"Calculation results for {k}: {v}")
                for item in biglist:
                    if k == item.uid:
                        item.LCA['Results'] = v
                        item.calculated = True

            self.logger.info("Calculations complete.")

            if write:
                text_label.setText("Writing results to file...")
                QApplication.processEvents()

                self.logger.info("Writing results to file.")
                import json
                out_file = open("mlca_dump.json", "w")
                json.dump(results, out_file, indent=4)
                self.logger.info("Results written to mlca_dump.json")

            text_label.setText("Calculations complete!")
            QTimer.singleShot(1000, spinner_dialog.accept)  # Close after 1 second



        except Exception as e:
            self.logger.error(f"Error during calculations: {e}")
            text_label.setText(f"Error during calculations: {str(e)}")
            QTimer.singleShot(3000, spinner_dialog.accept)  # Close after 3 seconds if error

        finally:
            # Always close the dialog when done
            if spinner_dialog.isVisible():
                spinner_dialog.accept()

            # update all LCA buttons in the application
            num_updated = self._updateAll_LCAButtons()
            self.logger.info(f"Updated the color of {num_updated} LCA buttons")

    def calculateAllLCAs_worker(self, write=False):
        """
        This method runs through every set of OutdoorDTOs and checks if they can have MLCAs run on them.
        Shows a spinner dialog during calculations. is deprecated in favor of calculateAllLCAs.

        This method was an attempt to use a worker thread for LCA calculations, but it is not used anymore.
        :param write:
        :return:
        """
        # spinner dialog
        dlg = QDialog()
        dlg.setWindowTitle("LCA calculation")
        dlg.setWindowFlags(dlg.windowFlags() & ~Qt.WindowContextHelpButtonHint & ~Qt.WindowCloseButtonHint)
        dlg.setFixedSize(300, 150)

        vbox = QVBoxLayout(dlg)
        spinner = QLabel(alignment=Qt.AlignCenter)
        text = QLabel("Collecting DTOs …", wordWrap=True, alignment=Qt.AlignCenter)

        movie_path = os.path.join(os.path.dirname(__file__), "loading.gif")
        self._movie = QMovie(movie_path, parent=dlg)  # keep reference!
        self._movie.setScaledSize(QSize(50, 50))
        spinner.setMovie(self._movie)
        self._movie.start()

        vbox.addWidget(spinner)
        vbox.addWidget(text)
        dlg.show()

        # prepare data
        biglist = (self.centralDataManager.componentData +
                   self.centralDataManager.wasteData +
                   self.centralDataManager.utilityData)
        inventory = []
        incomplete = {}
        incomplete_count = 0

        # Rest of your calculation code...
        for component in biglist:
            component.LCA['Results'] = {}
            if len(component.LCA['exchanges']) > 0:
                try:
                    inventory.append({self.outd.get(component.uid): 1})
                    self.logger.debug(f"Component {component.uid} has exchanges:{component.LCA['exchanges']}")
                except Exception as e:
                    self.logger.warning(f"Looks like component {component.name} hasn't been saved to BW yet.")
                    incomplete_count += 1
                    if component.__class__.__name__ in incomplete:
                        incomplete[component.__class__.__name__].append(component.name)
                    else:
                        incomplete[component.__class__.__name__] = [component.name]
            else:
                incomplete_count += 1
                if component.__class__.__name__ in incomplete:
                    incomplete[component.__class__.__name__].append(component.name)
                else:
                    incomplete[component.__class__.__name__] = [component.name]

        # Update status text
        #text_label.setText(f"Found {len(inventory)} DTOs ready for calculation. Processing...")
        QApplication.processEvents()

        self.logger.info(f"Identified {len(inventory)} DTOs ready for calculation")
        self.logger.warning(f"There are {len(incomplete)} DTOs that are not ready for calculation: {incomplete}")
        self.logger.info(f"Beginning calculations. This may take a while.")


        QApplication.processEvents()

        # ---------- launch worker thread ----------
        self._worker = LCAWorker(biglist, inventory,
                                 self.getImpactMethods(), write)
        self._worker.progress.connect(text.setText)
        self._worker.finished.connect(lambda _: dlg.accept())
        self._worker.errored.connect(lambda msg:
                                     (text.setText("Error: " + msg),
                                      QTimer.singleShot(3000, dlg.accept)))
        self._worker.start()

    def getImpactMethods(self) -> list:
        """
        Selects the correct methods (mid and or end-points) according to the LCA methodology selected by the user.
        returns: list of methods
        """
        if self.methodSelectionLCA == "ReCiPe 2016 v1.03 midpoint + endpoint (H)":
            return self._recipe_base_methods()

        elif self.methodSelectionLCA == "ReCiPe 2016 v1.1 midpoint + endpoint (H)":
            return self._recipe_V_1_1_methods()

        elif self.methodSelectionLCA == "IPCC 2013":
            return self._IPCC_methods()

        elif self.methodSelectionLCA == "ReCiPe 2016 v1.03 [bio=1] (custom: biogenic = fossil)":
            return self._ensure_biogenic_equals_fossil()

        else:
            self.logger.error("Method selection failed, using default method: "
                              "\n ReCipe 2016 v1.03 midpoint + endpoint (H)")
            return self._recipe_base_methods()
        # add other methods here if you want


    def getImpactDict(self):
        methods = self.getImpactMethods()
        results = {}
        for meth in methods:
            results[meth[2]] = (meth[3].split("(")[1].split(")")[0] if "midpoint" in str(meth) else meth[3], bw.Method(meth).metadata.get("unit"))
        return results

    def _updateAll_LCAButtons(self):
        """
        Find and update all LcaButton instances across the entire application.
        """
        # Get all top-level windows instead of just the active one
        all_windows = QApplication.topLevelWidgets()

        if not all_windows:
            self.logger.warning("No top-level widgets found in the application")
            return 0

        lca_buttons = []

        # Search through all top-level windows
        for window in all_windows:
            # Find all LcaButton instances in this window
            buttons = window.findChildren(LcaButton)
            if buttons:
                lca_buttons.extend(buttons)

        # Update each button
        updated_count = 0
        for button in lca_buttons:
            button.changeColorBnt()
            updated_count += 1

        return updated_count

    def _recipe_base_methods(self):
        """Default ReCiPe selections."""
        midpoint = [m for m in bw.methods
                    if "ReCiPe 2016 v1.03, midpoint (H)" in str(m) and "no LT" not in str(m)]
        endpoints = [m for m in bw.methods
                     if "ReCiPe 2016 v1.03, endpoint (H)" in str(m) and "no LT" not in str(m) and "total" in str(m)]
        return midpoint + endpoints

    def _recipe_V_1_1_methods(self):
        """ ReCiPe selections Version 1.1"""
        midpoint = [m for m in bw.methods
                    if "ReCiPe 2016 v1.1, midpoint (H)" in str(m) and "no LT" not in str(m)]
        endpoints = [m for m in bw.methods
                     if "ReCiPe 2016 v1.1, endpoint (H)" in str(m) and "no LT" not in str(m) and "total" in str(m)]
        return midpoint + endpoints

    def _IPCC_methods(self):
        """Original IPCC selections."""
        midpoints = [m for m in bw.methods if "IPCC 2013" in str(m) and "no LT" not in str(m)]
        return midpoints

    def _ensure_biogenic_equals_fossil(self) -> list:
        """
        Clone the currently selected ReCiPe methods and create '[BIO=1]' variants
        where biogenic CO2 is characterized as 1.0 (kg CO2-eq per kg biogenic CO2),
        instead of 0. Other flows (e.g., biogenic CH4) are untouched.

        Returns:
            List of new method keys you can use directly in MultiLCA.
        """
        base_methods = self._recipe_base_methods()  # reuse your current selection
        new_method_keys = []

        # Keys we will modify: ReCiPe GWP (midpoint) and (if present) any endpoint whose indicator mentions GWP
        def _is_gwp_indicator(meth_tuple):
            ind = str(meth_tuple[3]).lower()
            # typical strings include 'global warming potential (gwp100)'
            return ("global warming" in ind) or ("gwp" in ind)

        for meth in base_methods:
            orig = bw.Method(meth)
            try:
                cfs = list(orig.load())
            except Exception as e:
                self.logger.error(f"Couldn't load method {meth}: {e}")
                continue

            # Create a clean new key by tagging the indicator only (safer than altering top-level parts)
            new_key = (meth[0], f"{meth[1]} [BIO=1]", meth[2], meth[3])

            # If it already exists, keep it (or wipe & rebuild, your choice)
            if new_key in bw.methods:
                #bw.Method(new_key).deregister()
                self.logger.info(f"Custom method already exists: {new_key}")
                new_method_keys.append(new_key)
                continue

            # Only alter CFs when the indicator is GWP; otherwise write as an exact copy
            if _is_gwp_indicator(meth):
                new_cfs = []
                for row in cfs:
                    # CF rows are tuples like: (flow_key, amount) or (flow_key, amount, ...extras)
                    if not isinstance(row, tuple) or len(row) < 2:
                        new_cfs.append(row)
                        continue

                    flow_key, amount, *rest = row
                    try:
                        flow = bw.get_activity(flow_key)
                        if self._is_biogenic_co2_flow(flow):
                            amount = 1.0  # treat biogenic CO2 like fossil CO2
                    except Exception as e:
                        self.logger.debug(f"Flow lookup failed for {row}: {e}")

                    new_cfs.append((flow_key, amount, *rest))
            else:
                # Non-GWP indicators are copied as-is
                new_cfs = cfs

            # Register the new method
            try:
                new_m = bw.Method(new_key)
                meta = dict(orig.metadata) if getattr(orig, "metadata", None) else {}
                meta["comment"] = (meta.get("comment", "") + " | Biogenic CO2 set to 1.0 in GWP.").strip()
                new_m.register(**meta)
                new_m.write(new_cfs)
                new_method_keys.append(new_key)
                self.logger.info(f"Registered custom method: {new_key}")
            except Exception as e:
                self.logger.error(f"Failed to create custom method {new_key}: {e}")

        return new_method_keys

    def _is_biogenic_co2_flow(self, flow) -> bool:
        """
        Identify biogenic CO2 flows in the biosphere database.
        Targets common ecoinvent names:
          - 'Carbon dioxide, biogenic'
          - 'Carbon dioxide, from soil or biomass stock'
        """
        name = str(flow.get("name", "")).lower()
        if "carbon dioxide" in name and ("biogenic" in name or "from soil or biomass" in name):
            return True
        return False

######################################################################################################################

    def _biogenic_custom_key_old(self, mkey):
        """Rename method tuple so Brightway treats it as a new method namespace."""
        # Method keys are tuples like ('ReCiPe 2016 v1.03', 'midpoint (H)', 'climate change', 'GWP100')
        # We prepend a tag to the first element.
        return (f"{mkey[1]} [bio=1]",) + mkey[1:]

    def _biogenic_custom_key(self, mkey: tuple) -> tuple:
        """
        Return a new method key where the 'ReCiPe ...' segment is tagged with [bio=1].
        Works for 3- or 4-tuple method keys.
        """
        parts = list(mkey)
        # Find the segment that names the ReCiPe family
        idx = None
        for i, seg in enumerate(parts):
            if isinstance(seg, str) and "ReCiPe 2016" in seg:
                idx = i
                break
        if idx is None:
            # Fallback: tag the last segment to keep uniqueness
            idx = len(parts) - 1

        if "[bio=1]" not in parts[idx]:
            parts[idx] = f"{parts[idx]} [bio=1]"
        return tuple(parts)

    def _ensure_biogenic_equals_fossil_old(self) -> list:
        """
        Ensure custom ReCiPe methods exist where biogenic CO2 CF == fossil CO2 CF.
        Creates them on first run by cloning (register+write) originals; reuses later.
        """
        base_methods = self._recipe_base_methods()
        custom_methods = []

        # Locate CO2 flows once
        try:
            fossil_keys = {act.key for act in self.bios if act.get('name') == 'Carbon dioxide, fossil'}
            biogenic_keys = {act.key for act in self.bios if act.get('name') == 'Carbon dioxide' and 'fossil' not in act.get('name')}
            # a = {act for act in self.bios if 'Carbon dioxide' in act.get('name')}

            if not fossil_keys:
                self.logger.warning("fossil CO2 flows not found. Custom methods will be unpatched clones.")
            elif not biogenic_keys:
                self.logger.warning("biogenic CO2 flows not found. Custom methods will be unpatched clones.")

        except Exception as e:
            self.logger.error(f"Scanning biosphere failed: {e}")
            fossil_keys, biogenic_keys = set(), set()

        for m in base_methods:
            new_key = self._biogenic_custom_key(m)

            # Reuse if already exists
            if new_key in bw.methods:
                self.logger.debug(f"Reusing custom method: {new_key}")
                custom_methods.append(new_key)
                continue

            # --- Create: register + write CFs from original ---
            try:
                orig = bw.Method(m)
                cfs = list(orig.load())
            except Exception as e:
                self.logger.error(f"Failed to load original method {m}: {e}")
                continue

            try:
                new = bw.Method(new_key)
                # Copy minimal metadata if available
                meta = getattr(orig, "metadata", {}) or {}
                unit = meta.get("unit")
                desc = meta.get("description") or "Custom ReCiPe with biogenic CO2 treated as fossil"
                # Register (unit/description are optional kwargs in Brightway)
                if unit:
                    new.register(unit=unit, description=desc)
                else:
                    new.register(description=desc)
                # Write original CFs first (as an exact clone)
                new.write(cfs)
                self.logger.info(f"Created custom method: {new_key}")
            except Exception as e:
                self.logger.error(f"Failed to register/write custom method {new_key}: {e}")
                continue

            # --- Patch: set biogenic CF == fossil CF (if both present) ---
            try:
                # Find fossil CF in this method’s CFs
                fossil_cf = None
                for row in cfs:
                    fk, val, *rest = row
                    if fk in fossil_keys:
                        fossil_cf = val
                        break

                if fossil_cf is not None and biogenic_keys:
                    patched = []
                    changed = 0
                    for row in cfs:
                        fk, val, *rest = row
                        if fk in biogenic_keys and val != fossil_cf:
                            patched.append((fk, fossil_cf, *rest))
                            changed += 1
                        else:
                            patched.append(row)
                    new.write(patched)  # overwrite with patched CF set
                    self.logger.info(f"Patched {changed} biogenic CFs in {new_key} to fossil CF={fossil_cf}.")
                else:
                    self.logger.warning(f"{new_key}: fossil CF not found or no biogenic flow; left unpatched.")
            except Exception as e:
                self.logger.error(f"Patching failed for {new_key}: {e}")

            custom_methods.append(new_key)

        return custom_methods



