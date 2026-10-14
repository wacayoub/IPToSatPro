# -*- coding: utf-8 -*-
"""VuLink v0.1 - Enigma2 read-only LAN pairing screen (no FTP/SSH exposure)."""
import os
import tempfile
from pathlib import Path

from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap

from .bridge import PairingServer, create_qr_image


class VuLinkScreen(Screen):
    skin = """
    <screen name="VuLinkScreen" position="center,center" size="1160,640"
            title="VuLink • Appairage diagnostic" backgroundColor="#0C1722">
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
      <widget name="hint" position="42,398" size="700,120" font="Regular;20"
              foregroundColor="#B4C9DB" transparent="1" />
      <eLabel position="797,161" size="276,276" backgroundColor="#FFFFFF" />
      <widget name="qr" position="805,169" size="260,260"
              alphatest="on" zPosition="4" />
      <widget name="qr_fallback" position="811,226" size="249,140"
              font="Regular;20" halign="center" foregroundColor="#101923"
              transparent="1" zPosition="3" />
      <eLabel position="28,564" size="1100,52" backgroundColor="#182D3E" />
      <widget name="key_red" position="50,574" size="1000,34"
              font="Regular;21" foregroundColor="#EAA4A4" transparent="1" />
    </screen>
    """

    def __init__(self, session):
        Screen.__init__(self, session)
        self.pair = None
        self.qr_path = ""
        self["title"] = Label("VuLink  •  DIAGNOSTIC LOCAL")
        self["status"] = Label("Initialisation de la session temporaire...")
        self["instructions"] = Label("1. Connecte ton telephone au meme reseau Wi-Fi.\n"
                                      "2. Scanne le QR ou entre le code ci-dessous.")
        self["address"] = Label("Adresse : —")
        self["code"] = Label("Code : —")
        self["hint"] = Label("3. Telecharge le rapport JSON sur ton telephone.\n"
                              "4. Ajoute-le dans notre conversation ChatGPT.\n"
                              "Aucun mot de passe, mapping ou URL IPTV transmis.")
        self["qr"] = Pixmap()
        self["qr_fallback"] = Label("QR optionnel\nUtilise l'adresse\net le code")
        self["key_red"] = Label("ROUGE / EXIT : arreter le partage immediatement")
        self["actions"] = ActionMap(
            ["OkCancelActions", "ColorActions"],
            {"ok": self.close, "cancel": self.close, "red": self.close},
            -2
        )
        self.onLayoutFinish.append(self._open)
        self.onClose.append(self._cleanup)

    def _open(self):
        try:
            self.pair = PairingServer()
            self.pair.start()
            code = self.pair.code
            self["address"].setText("Adresse : " + self.pair.base_url)
            self["code"].setText("Code : %s-%s-%s" % (code[:4], code[4:8], code[8:]))
            self["status"].setText("SESSION ACTIVE • Lecture seule • Expire apres 10 min")
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

    def _cleanup(self):
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
        PluginDescriptor(name="VuLink - Connexion QR diagnostic",
                         description="Appairage local temporaire, rapport sans secrets",
                         where=PluginDescriptor.WHERE_PLUGINMENU,
                         fnc=open_vulink),
        PluginDescriptor(name="VuLink - Connexion QR diagnostic",
                         description="Ouvrir une session diagnostic en lecture seule",
                         where=PluginDescriptor.WHERE_EXTENSIONSMENU,
                         fnc=open_vulink),
    ]
