# -*- coding: utf-8 -*-
"""VuLink Pro V2 - on-TV approved maintenance via LAN pairing (no SSH tunnel)."""
import os
import tempfile
from pathlib import Path

from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap

from .bridge import create_qr_image
from .v2 import ProPairingServer
from enigma import eTimer


class VuLinkScreen(Screen):
    skin = """
    <screen name="VuLinkScreen" position="center,center" size="1160,640"
            title="VuLink Pro V2 • Maintenance locale" backgroundColor="#0C1722">
      <eLabel position="0,0" size="1160,74" backgroundColor="#192B3B" />
      <widget name="title" position="38,20" size="1070,36" font="Regular;31"
              foregroundColor="#FFFFFF" transparent="1" />
      <widget name="status" position="42,97" size="1050,39" font="Regular;22"
              foregroundColor="#7CE2C9" transparent="1" />
      <widget name="instructions" position="42,146" size="700,76"
              font="Regular;22" foregroundColor="#CBDCE9" transparent="1" />
      <widget name="address" position="42,253" size="700,45" font="Regular;23"
              foregroundColor="#FFFFFF" transparent="1" />
      <widget name="code" position="42,325" size="700,47" font="Regular;33"
              foregroundColor="#FFDD78" transparent="1" />
      <widget name="hint" position="42,392" size="700,100" font="Regular;20"
              foregroundColor="#B4C9DB" transparent="1" />
      <eLabel position="797,161" size="276,276" backgroundColor="#FFFFFF" />
      <widget name="qr" position="805,169" size="260,260"
              alphatest="on" zPosition="4" />
      <widget name="qr_fallback" position="811,226" size="249,140"
              font="Regular;20" halign="center" foregroundColor="#101923"
              transparent="1" zPosition="3" />
      <widget name="approval" position="42,497" size="1000,57" font="Regular;21" foregroundColor="#FFDD78" transparent="1" />
      <eLabel position="28,564" size="1100,52" backgroundColor="#182D3E" />
      <widget name="key_red" position="50,574" size="1000,34"
              font="Regular;21" foregroundColor="#EAA4A4" transparent="1" />
    </screen>
    """

    def __init__(self, session):
        Screen.__init__(self, session)
        self.pair = None
        self.qr_path = ""
        self._pending_id = None
        self.approval_timer = eTimer()
        self.approval_timer.callback.append(self._refresh)
        self["title"] = Label("VuLink PRO V2 • DIAGNOSTIC & MAINTENANCE")
        self["status"] = Label("Initialisation de la session temporaire...")
        self["instructions"] = Label("1. Connecte ton telephone au meme reseau Wi-Fi.\n"
                                      "2. Scanne le QR ou entre le code ci-dessous.")
        self["address"] = Label("Adresse : —")
        self["code"] = Label("Code : —")
        self["hint"] = Label("3. Rapport JSON disponible sur le telephone.\n"
                              "4. Pour une action, confirme sur la TV.\n"
                              "Aucun acces SSH/FTP ni secret transmis.")
        self["approval"] = Label("Aucune action en attente")
        self["qr"] = Pixmap()
        self["qr_fallback"] = Label("QR optionnel\nUtilise l'adresse\net le code")
        self["key_red"] = Label("VERT : APPROUVER • JAUNE : REFUSER • ROUGE/EXIT : FERMER")
        self["actions"] = ActionMap(
            ["OkCancelActions", "ColorActions"],
            {"ok": self.close, "cancel": self.close, "red": self.close,
             "green": self._approve, "yellow": self._deny},
            -2
        )
        self.onLayoutFinish.append(self._open)
        self.onClose.append(self._cleanup)

    def _open(self):
        try:
            self.pair = ProPairingServer()
            self.pair.start()
            code = self.pair.code
            self["address"].setText("Adresse : " + self.pair.base_url)
            self["code"].setText("Code : %s-%s-%s" % (code[:4], code[4:8], code[8:]))
            self["status"].setText("SESSION PRO V2 • QR local • 10 min • Actions sur accord TV")
            self.approval_timer.start(1000, False)
            fd, path = tempfile.mkstemp(prefix="vulink-qr-", suffix=".png")
            os.close(fd)
            self.qr_path = path
            if create_qr_image(self.pair.url, path):
                try:
                    self["qr"].instance.setPixmapFromFile(path)
                    self["qr_fallback"].hide()
                except Exception:
                    self["qr_fallback"].show()
            else:
                self["qr_fallback"].show()
        except Exception as exc:
            self["status"].setText("Connexion LAN indisponible : " + str(exc)[:100])
            self["hint"].setText("Controle que le Vu+ est relie au reseau.\n"
                                  "Aucune modification n'a ete effectuee.")
            self._cleanup()

    def _refresh(self):
        if self.pair is None:
            return
        pending = self.pair.pending()
        self._pending_id = pending[0] if pending else None
        if pending:
            self["approval"].setText("CONFIRMER : " + pending[1]["title"][:70])
        else:
            state = self.pair.public_state()
            if state["expires_in_seconds"] <= 0:
                self["approval"].setText("Session expiree • Ferme et rouvre VuLink.")
            elif state["busy"]:
                self["approval"].setText("Action autorisee en cours...")
            elif state["last_action"]:
                self["approval"].setText("Action : " + state["last_action"]["status"])
            else:
                self["approval"].setText("Aucune action en attente")

    def _approve(self):
        if self.pair is not None and self._pending_id:
            self.pair.decide(self._pending_id, True)
            self._refresh()

    def _deny(self):
        if self.pair is not None and self._pending_id:
            self.pair.decide(self._pending_id, False)
            self._refresh()

    def _cleanup(self):
        try:
            self.approval_timer.stop()
        except Exception:
            pass
        if self.pair is not None:
            try:
                self.pair.stop()
            except Exception:
                pass
            self.pair = None
        if self.qr_path:
            try:
                Path(self.qr_path).unlink(missing_ok=True)
            except Exception:
                pass
            self.qr_path = ""


def open_vulink(session, **_kwargs):
    session.open(VuLinkScreen)


def Plugins(**_kwargs):
    return [
        PluginDescriptor(name="VuLink Pro V2 - QR Maintenance",
                         description="Diagnostic et maintenance locale sur accord du Vu+",
                         where=PluginDescriptor.WHERE_PLUGINMENU,
                         fnc=open_vulink),
        PluginDescriptor(name="VuLink Pro V2 - QR Maintenance",
                         description="Ouvrir une session de maintenance privee",
                         where=PluginDescriptor.WHERE_EXTENSIONSMENU,
                         fnc=open_vulink),
    ]
