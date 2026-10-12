# -*- coding: utf-8 -*-
"""R74 compact, legible Neo Dark FHD skin for real Enigma2 (1700x790).

Single title, two strictly separated pane headings, two concise status lines,
five color-key zones; no overlapping widget rectangles and no external fonts.
"""
PREVIEW_R74_FHD = """
<screen name="SatIPTVBridgePreview" position="center,center" size="1700,790"
 title="IPToSatPro Preview Browser R74" flags="wfNoBorder" backgroundColor="#08131E">
  <eLabel zPosition="0" position="0,0" size="1700,5" backgroundColor="#31D5B4" />
  <eLabel zPosition="0" position="24,14" size="1652,63" backgroundColor="#112433" />
  <eLabel zPosition="0" position="24,86" size="1652,116" backgroundColor="#102130" />
  <eLabel zPosition="0" position="24,213" size="530,419" backgroundColor="#142431" />
  <eLabel zPosition="0" position="566,213" size="1110,419" backgroundColor="#142431" />
  <eLabel zPosition="0" position="24,213" size="530,4" backgroundColor="#31D5B4" />
  <eLabel zPosition="0" position="566,213" size="1110,4" backgroundColor="#66A5DC" />
  <eLabel zPosition="0" position="24,640" size="1652,66" backgroundColor="#102130" />
  <widget name="title" position="43,27" size="990,38" zPosition="3"
    font="Regular;29" foregroundColor="#F5F9FF" transparent="1" />
  <widget name="focus_hint" position="1070,29" size="572,28" zPosition="3"
    font="Regular;18" halign="right" foregroundColor="#31D5B4" transparent="1" />
  <eLabel zPosition="1" position="37,96" size="151,93" backgroundColor="#1A3443" />
  <widget name="sat_picon" position="46,105" size="132,74" zPosition="3"
    alphatest="on" scale="1" />
  <widget name="picon_fallback" position="46,109" size="132,69" zPosition="2"
    font="Regular;16" halign="center" valign="center"
    foregroundColor="#94ADBD" transparent="1" />
  <widget name="sat_current" position="206,97" size="1424,31" zPosition="3"
    font="Regular;23" foregroundColor="#F8DCA3" transparent="1" />
  <widget name="context_info" position="206,131" size="1424,24" zPosition="3"
    font="Regular;17" foregroundColor="#B5CCDE" transparent="1" />
  <widget name="epg" position="206,156" size="1424,21" zPosition="3"
    font="Regular;17" foregroundColor="#E3F0F9" transparent="1" />
  <widget name="status" position="206,181" size="1012,20" zPosition="3"
    font="Regular;16" foregroundColor="#4ED9B4" transparent="1" />
  <widget name="subtitles" position="1230,181" size="402,20" zPosition="3"
    font="Regular;16" halign="right" foregroundColor="#A4C8E8" transparent="1" />
  <widget name="left_head" position="41,223" size="496,28" zPosition="3"
    font="Regular;20" foregroundColor="#5FEAC6" transparent="1" />
  <widget name="right_head" position="583,223" size="1067,28" zPosition="3"
    font="Regular;20" foregroundColor="#91CBFA" transparent="1" />
  <widget name="sat_list" position="38,258" size="497,358" zPosition="3"
    itemHeight="43" font="Regular;19" foregroundColor="#F0F6FA"
    backgroundColor="#142431" scrollbarMode="showOnDemand" />
  <widget name="source_list" position="580,258" size="1073,358" zPosition="3"
    itemHeight="43" font="Regular;18" foregroundColor="#F0F6FA"
    backgroundColor="#142431" scrollbarMode="showOnDemand" />
  <widget name="verify" position="40,646" size="1610,23" zPosition="3"
    font="Regular;17" foregroundColor="#C3D7E5" transparent="1" />
  <widget name="detail" position="40,677" size="1610,23" zPosition="3"
    font="Regular;17" foregroundColor="#A7BDD0" transparent="1" />
  <eLabel position="24,716" size="313,54" zPosition="0" backgroundColor="#A23E4C" />
  <eLabel position="349,716" size="313,54" zPosition="0" backgroundColor="#16855E" />
  <eLabel position="674,716" size="313,54" zPosition="0" backgroundColor="#A1802D" />
  <eLabel position="999,716" size="313,54" zPosition="0" backgroundColor="#246F9F" />
  <eLabel position="1324,716" size="352,54" zPosition="0" backgroundColor="#554581" />
  <widget name="key_red" position="24,718" size="313,50" zPosition="3"
    font="Regular;19" halign="center" valign="center" foregroundColor="#FFFFFF" transparent="1" />
  <widget name="key_green" position="349,718" size="313,50" zPosition="3"
    font="Regular;19" halign="center" valign="center" foregroundColor="#FFFFFF" transparent="1" />
  <widget name="key_yellow" position="674,718" size="313,50" zPosition="3"
    font="Regular;19" halign="center" valign="center" foregroundColor="#FFFFFF" transparent="1" />
  <widget name="key_blue" position="999,718" size="313,50" zPosition="3"
    font="Regular;19" halign="center" valign="center" foregroundColor="#FFFFFF" transparent="1" />
  <widget name="key_menu" position="1324,718" size="352,50" zPosition="3"
    font="Regular;18" halign="center" valign="center" foregroundColor="#FFFFFF" transparent="1" />
</screen>
"""
