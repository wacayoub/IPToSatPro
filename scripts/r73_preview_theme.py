# -*- coding: utf-8 -*-
"""R73 Preview Browser Pro - light-weight Enigma2 native Neo Dark skin.

No external fonts, PNG rendering, picon decoding in the skin, image loops, or
non-standard GUI components. The existing widget names are retained exactly.
"""
PREVIEW_R73_FHD = """
<screen name="SatIPTVBridgePreview" position="center,center" size="1700,790"
 title="IPToSatPro - Preview Browser Pro R73" backgroundColor="#090F18" flags="wfNoBorder">
  <eLabel zPosition="0" position="0,0" size="1700,6" backgroundColor="#27C7AC" />
  <eLabel zPosition="0" position="24,16" size="1652,65" backgroundColor="#111C29" />
  <eLabel zPosition="0" position="24,91" size="1652,112" backgroundColor="#101C29" />
  <eLabel zPosition="0" position="24,213" size="532,417" backgroundColor="#121F2D" />
  <eLabel zPosition="0" position="567,213" size="1109,417" backgroundColor="#121F2D" />
  <eLabel zPosition="1" position="24,213" size="532,4" backgroundColor="#27C7AC" />
  <eLabel zPosition="1" position="567,213" size="1109,4" backgroundColor="#347BA5" />
  <eLabel zPosition="0" position="24,638" size="1652,71" backgroundColor="#101C29" />
  <eLabel zPosition="0" position="34,104" size="148,86" backgroundColor="#192C3A" />
  <widget name="title" zPosition="3" position="42,26" size="1070,39" font="Regular;29"
          foregroundColor="#F5F9FF" transparent="1" />
  <widget name="focus_hint" zPosition="3" position="1150,29" size="492,29" font="Regular;20"
          halign="right" foregroundColor="#30D5B4" transparent="1" />
  <widget name="sat_picon" zPosition="3" position="42,111" size="132,72" alphatest="on" scale="1" />
  <widget name="picon_fallback" zPosition="2" position="42,111" size="132,72"
          font="Regular;15" halign="center" valign="center" foregroundColor="#819AAD" transparent="1" />
  <widget name="sat_current" zPosition="3" position="199,102" size="1429,30"
          font="Regular;23" foregroundColor="#F9D981" transparent="1" />
  <widget name="context_info" zPosition="3" position="199,133" size="1429,23"
          font="Regular;17" foregroundColor="#B0C4D4" transparent="1" />
  <widget name="epg" zPosition="3" position="199,157" size="1429,23"
          font="Regular;17" foregroundColor="#D5E9F5" transparent="1" />
  <widget name="status" zPosition="3" position="199,181" size="1022,22"
          font="Regular;16" foregroundColor="#55D9BA" transparent="1" />
  <widget name="subtitles" zPosition="3" position="1238,181" size="390,22"
          font="Regular;16" halign="right" foregroundColor="#9DC9E6" transparent="1" />
  <widget name="left_head" zPosition="3" position="40,222" size="501,29"
          font="Regular;20" foregroundColor="#69E1C3" transparent="1" />
  <widget name="right_head" zPosition="3" position="585,222" size="1050,29"
          font="Regular;20" foregroundColor="#89CFFF" transparent="1" />
  <widget name="sat_list" zPosition="3" position="38,256" size="501,363"
          itemHeight="42" font="Regular;19" scrollbarMode="showOnDemand"
          foregroundColor="#ECF4F8" backgroundColor="#121F2D" />
  <widget name="source_list" zPosition="3" position="583,256" size="1073,363"
          itemHeight="42" font="Regular;18" scrollbarMode="showOnDemand"
          foregroundColor="#ECF4F8" backgroundColor="#121F2D" />
  <widget name="verify" zPosition="3" position="41,645" size="1608,25"
          font="Regular;17" foregroundColor="#A8BED0" transparent="1" />
  <widget name="detail" zPosition="3" position="41,673" size="1608,30"
          font="Regular;17" foregroundColor="#E7F1FA" transparent="1" />
  <eLabel zPosition="0" position="24,719" size="313,51" backgroundColor="#8A343E" />
  <eLabel zPosition="0" position="349,719" size="313,51" backgroundColor="#257955" />
  <eLabel zPosition="0" position="674,719" size="313,51" backgroundColor="#A78129" />
  <eLabel zPosition="0" position="999,719" size="313,51" backgroundColor="#286B9A" />
  <eLabel zPosition="0" position="1324,719" size="352,51" backgroundColor="#473E69" />
  <widget name="key_red" zPosition="3" position="24,719" size="313,51"
          font="Regular;19" halign="center" valign="center" foregroundColor="#FFFFFF" transparent="1" />
  <widget name="key_green" zPosition="3" position="349,719" size="313,51"
          font="Regular;19" halign="center" valign="center" foregroundColor="#FFFFFF" transparent="1" />
  <widget name="key_yellow" zPosition="3" position="674,719" size="313,51"
          font="Regular;19" halign="center" valign="center" foregroundColor="#FFFFFF" transparent="1" />
  <widget name="key_blue" zPosition="3" position="999,719" size="313,51"
          font="Regular;19" halign="center" valign="center" foregroundColor="#FFFFFF" transparent="1" />
  <widget name="key_menu" zPosition="3" position="1324,719" size="352,51"
          font="Regular;17" halign="center" valign="center" foregroundColor="#FFFFFF" transparent="1" />
</screen>
"""
