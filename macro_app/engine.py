"""
macro_app/engine.py
Moteur d'execution des macros.

Classes :
  _GotoSignal   — exception interne pour les sauts d'etiquette
  MacroEngine   — execution en thread daemon, support label/goto
"""

import os
import time

from .utils import WINDOWS, PIL_AVAILABLE, Image, ImageGrab, ImageChops

try:
    import ctypes
    import ctypes.wintypes
except ImportError:
    ctypes = None


# ─────────────────────────────────────────────
#  SIGNAL INTERNE DE SAUT
# ─────────────────────────────────────────────
class _GotoSignal(Exception):
    """Levee par un noeud 'goto' pour sauter a une etiquette."""
    def __init__(self, target: str):
        self.target = target


class _ReturnSignal(Exception):
    """Levee par stop_return pour stopper la macro et retourner une valeur."""
    def __init__(self, value: bool):
        self.value = value


# ─────────────────────────────────────────────
#  MOTEUR D'EXECUTION
# ─────────────────────────────────────────────
class MacroEngine:
    def __init__(self, macro: dict, on_step=None, on_done=None, on_error=None,
                 macros_list=None, _parent=None, debug_overlay: bool = False):
        self.macro        = macro
        self.on_step      = on_step
        self.on_done      = on_done
        self.on_error     = on_error
        self._parent      = _parent        # moteur parent pour call_macro
        self._macros_list = macros_list    # toutes les macros du fichier ouvert
        self._debug_overlay = debug_overlay
        self.__stop       = False
        self.__pause      = False
        self._vars: dict         = {}   # variables numeriques (double) de la macro
        self._return_value: bool = False  # valeur retournee par stop_return

        # Facteurs d'echelle resolution (macro enregistree vs ecran actuel)
        self._sx: float = 1.0
        self._sy: float = 1.0
        rec_w = int(macro.get("res_w", 0))
        rec_h = int(macro.get("res_h", 0))
        if rec_w > 0 and rec_h > 0 and WINDOWS and ctypes:
            cur_w = ctypes.windll.user32.GetSystemMetrics(0)  # SM_CXSCREEN
            cur_h = ctypes.windll.user32.GetSystemMetrics(1)  # SM_CYSCREEN
            if cur_w > 0 and cur_h > 0:
                self._sx = cur_w / rec_w
                self._sy = cur_h / rec_h

    # ── Propagation stop/pause depuis le moteur parent ──
    @property
    def _stop(self) -> bool:
        if self._parent is not None and self._parent._stop:
            return True
        return self.__stop

    @_stop.setter
    def _stop(self, val: bool) -> None:
        self.__stop = val

    @property
    def _pause(self) -> bool:
        if self._parent is not None and self._parent._pause:
            return True
        return self.__pause

    @_pause.setter
    def _pause(self, val: bool) -> None:
        self.__pause = val

    # ── Controle ──────────────────────────────
    def stop(self):   self._stop  = True
    def pause(self):  self._pause = True
    def resume(self): self._pause = False

    def _sc(self, x: int, y: int) -> tuple:
        """Applique le facteur d'echelle resolution sur des coordonnees."""
        if self._sx == 1.0 and self._sy == 1.0:
            return x, y
        return round(x * self._sx), round(y * self._sy)

    # ── Boucle principale ─────────────────────
    def run(self):
        try:
            self._run_top_level(self.macro["nodes"])
            if self.macro.get("loop") and not self._stop:
                self._stop = False
                self.run()
            else:
                if self.on_done:
                    self.on_done()
        except Exception as e:
            if self.on_error:
                self.on_error(str(e))

    def _run_top_level(self, nodes: list) -> None:
        """Execute la liste racine avec support label/goto (index-based)."""
        # Pre-collecte des etiquettes : nom -> index
        labels = {}
        for i, node in enumerate(nodes):
            if node["type"] == "label":
                name = node["params"].get("name", "").strip()
                if name:
                    labels[name] = i

        idx = 0
        while idx < len(nodes):
            if self._stop:
                return
            while self._pause:
                time.sleep(0.1)
                if self._stop:
                    return
            node = nodes[idx]
            if self.on_step:
                self.on_step(node["id"])
            try:
                self._execute_node(node)
                idx += 1
            except _GotoSignal as g:
                target = g.target.strip()
                if target in labels:
                    idx = labels[target]
                else:
                    raise ValueError(f"Etiquette introuvable: '{target}'")
            except _ReturnSignal as r:
                self._return_value = r.value
                self._stop = True
                return

    def _execute_nodes(self, nodes: list) -> None:
        """Execute une branche (enfants de condition/boucle).
        Un _GotoSignal se propage naturellement vers _run_top_level.
        """
        for node in nodes:
            if self._stop:
                return
            while self._pause:
                time.sleep(0.1)
                if self._stop:
                    return
            if self.on_step:
                self.on_step(node["id"])
            self._execute_node(node)

    # ── Dispatch par type de noeud ────────────
    def _execute_node(self, node: dict) -> None:
        t = node["type"]
        p = node["params"]

        if t == "action_click":
            x, y = self._sc(int(p.get("x", 0)), int(p.get("y", 0)))
            self._mouse_click(x, y, p.get("button", "left"), int(p.get("count", 1)))

        elif t == "action_move":
            x, y = self._sc(int(p.get("x", 0)), int(p.get("y", 0)))
            self._mouse_move(x, y)

        elif t == "action_scroll":
            x, y = self._sc(int(p.get("x", 0)), int(p.get("y", 0)))
            self._mouse_scroll(x, y, int(p.get("delta", 3)))

        elif t == "action_key":
            self._send_keys(p.get("keys", ""))

        elif t == "action_type":
            self._type_text(p.get("text", ""))

        elif t == "action_wait":
            end = time.time() + float(p.get("ms", 1000)) / 1000.0
            while time.time() < end:
                if self._stop:
                    return
                time.sleep(0.05)

        elif t == "action_run":
            cmd = p.get("command", "")
            if cmd:
                os.startfile(cmd) if os.path.exists(cmd) else os.system(cmd)

        elif t == "action_focus":
            self._focus_window(p.get("title", ""), bool(p.get("partial", True)))

        elif t in ("condition_screen", "condition_pixel"):
            result = (self._check_screen_image(p, single_shot=True)
                      if t == "condition_screen"
                      else self._check_pixel_color(p))
            children    = node.get("children", [[], []])
            true_nodes  = children[0] if len(children) > 0 else []
            false_nodes = children[1] if len(children) > 1 else []
            self._execute_nodes(true_nodes if result else false_nodes)

        elif t == "loop_count":
            count = int(p.get("count", 1))
            for _ in range(count):
                if self._stop:
                    break
                self._execute_nodes(node.get("children", [[]])[0])

        elif t == "loop_while":
            max_iter = int(p.get("max_iter", 100))
            for _ in range(max_iter):
                if self._stop:
                    break
                if not self._check_screen_image(p):
                    break
                self._execute_nodes(node.get("children", [[]])[0])

        elif t == "label":
            pass   # marqueur uniquement, traite par _run_top_level

        elif t == "goto":
            target = p.get("target", "").strip()
            if target:
                raise _GotoSignal(target)

        elif t == "stop":
            self._stop = True

        elif t == "stop_return":
            val = str(p.get("value", "False")) == "True"
            raise _ReturnSignal(val)
            name = p.get("name", "").strip()
            if name:
                try:
                    self._vars[name] = float(p.get("value", 0))
                except (ValueError, TypeError):
                    self._vars[name] = 0.0

        elif t == "var_add":
            name = p.get("name", "").strip()
            if name:
                try:
                    delta = float(p.get("delta", 0))
                except (ValueError, TypeError):
                    delta = 0.0
                self._vars[name] = self._vars.get(name, 0.0) + delta

        elif t == "condition_var":
            name = p.get("name", "").strip()
            op   = p.get("op", "==")
            try:
                ref = float(p.get("ref", 0))
            except (ValueError, TypeError):
                ref = 0.0
            val = self._vars.get(name, 0.0)
            result = {
                "==": val == ref,
                "!=": val != ref,
                ">":  val > ref,
                "<":  val < ref,
                ">=": val >= ref,
                "<=": val <= ref,
            }.get(op, False)
            children    = node.get("children", [[], []])
            true_nodes  = children[0] if len(children) > 0 else []
            false_nodes = children[1] if len(children) > 1 else []
            self._execute_nodes(true_nodes if result else false_nodes)

        elif t == "loop_while_var":
            name    = p.get("name", "").strip()
            op      = p.get("op", "==")
            try:
                ref = float(p.get("ref", 0))
            except (ValueError, TypeError):
                ref = 0.0
            max_iter = int(p.get("max_iter", 10000))
            body = node.get("children", [[]])[0]
            for _ in range(max_iter):
                if self._stop:
                    break
                val = self._vars.get(name, 0.0)
                should_continue = {
                    "==": val == ref, "!=": val != ref,
                    ">":  val > ref,  "<":  val < ref,
                    ">=": val >= ref, "<=": val <= ref,
                }.get(op, False)
                if not should_continue:
                    break
                self._execute_nodes(body)

        elif t == "condition_group":
            logic = p.get("logic", "AND")
            conds = p.get("conditions", [])
            if conds:
                results = [self._eval_sub_condition(c) for c in conds]
                result  = all(results) if logic == "AND" else any(results)
            else:
                result = True
            children    = node.get("children", [[], []])
            true_nodes  = children[0] if len(children) > 0 else []
            false_nodes = children[1] if len(children) > 1 else []
            self._execute_nodes(true_nodes if result else false_nodes)

        elif t == "call_macro":
            macro_name = p.get("macro_name", "").strip()
            return_val = False
            if macro_name and self._macros_list:
                target = next(
                    (m for m in self._macros_list if m.get("name") == macro_name),
                    None
                )
                if target:
                    sub = MacroEngine(
                        target,
                        macros_list=self._macros_list,
                        on_step=self.on_step,
                        on_done=None,
                        on_error=self.on_error,
                        _parent=self,
                    )
                    sub._vars = self._vars   # partage les variables
                    sub._run_top_level(target["nodes"])
                    return_val = sub._return_value
            children    = node.get("children", [[], []])
            true_nodes  = children[0] if len(children) > 0 else []
            false_nodes = children[1] if len(children) > 1 else []
            self._execute_nodes(true_nodes if return_val else false_nodes)

        elif t == "record_replay":
            self._exec_record_replay(p)

    # ── Enregistrement / Relecture d'inputs ───
    def _exec_record_replay(self, p: dict) -> None:
        """Rejoue les actions enregistrees dans le noeud via l'editeur."""
        actions = p.get("actions", [])
        if not actions or not WINDOWS or not ctypes:
            return

        user32     = ctypes.windll.user32
        mouse_mode = p.get("mouse_mode", "absolute")

        if mouse_mode == "relative":
            pt = ctypes.wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            ox, oy = pt.x, pt.y
        else:
            ox, oy = 0, 0

        LD, LU = 0x0002, 0x0004
        RD, RU = 0x0008, 0x0010
        MD, MU = 0x0020, 0x0040
        BTN_DN = {"left": LD, "right": RD, "middle": MD}
        BTN_UP = {"left": LU, "right": RU, "middle": MU}

        for act in actions:
            if self._stop:
                break
            dt = act.get("dt", 0.0)
            if dt > 0:
                end = time.time() + dt
                while time.time() < end:
                    if self._stop:
                        return
                    time.sleep(max(0.0, min(0.005, end - time.time())))
            at = act["t"]
            ax = round(act.get("x", 0) * self._sx) + ox
            ay = round(act.get("y", 0) * self._sy) + oy
            if at == "move":
                user32.SetCursorPos(ax, ay)
            elif at == "click_dn":
                user32.SetCursorPos(ax, ay)
                user32.mouse_event(BTN_DN.get(act.get("btn", "left"), LD), 0, 0, 0, 0)
            elif at == "click_up":
                user32.SetCursorPos(ax, ay)
                user32.mouse_event(BTN_UP.get(act.get("btn", "left"), LU), 0, 0, 0, 0)
            elif at == "scroll":
                user32.SetCursorPos(ax, ay)
                user32.mouse_event(0x0800, 0, 0, act.get("delta", 1) * 120, 0)
            elif at == "key_dn":
                user32.keybd_event(act["vk"], 0, 0, 0)
            elif at == "key_up":
                user32.keybd_event(act["vk"], 0, 0x0002, 0)

    # ── Actions bas niveau Windows ────────────
    def _eval_sub_condition(self, cond: dict) -> bool:
        """Evalue une sous-condition (type 'var' ou 'pixel') pour condition_group."""
        ct = cond.get("type", "")
        if ct == "var":
            name = cond.get("name", "").strip()
            op   = cond.get("op", "==")
            try:
                ref = float(cond.get("ref", 0))
            except (ValueError, TypeError):
                ref = 0.0
            val = self._vars.get(name, 0.0)
            return {
                "==": val == ref, "!=": val != ref,
                ">":  val > ref,  "<":  val < ref,
                ">=": val >= ref, "<=": val <= ref,
            }.get(op, False)
        elif ct == "pixel":
            if not PIL_AVAILABLE or not ImageGrab:
                return False
            x, y = self._sc(int(cond.get("x", 0)), int(cond.get("y", 0)))
            r   = int(cond.get("r", 0))
            g   = int(cond.get("g", 0))
            b   = int(cond.get("b", 0))
            tol = int(cond.get("tolerance", 10))
            try:
                px = ImageGrab.grab(bbox=(x, y, x + 1, y + 1)).getpixel((0, 0))
                return (abs(px[0] - r) <= tol and
                        abs(px[1] - g) <= tol and
                        abs(px[2] - b) <= tol)
            except Exception:
                return False
        return True

    def _mouse_move(self, x: int, y: int) -> None:
        if WINDOWS and ctypes:
            ctypes.windll.user32.SetCursorPos(x, y)
        time.sleep(0.03)

    def _mouse_click(self, x: int, y: int, button: str = "left", count: int = 1) -> None:
        self._mouse_move(x, y)
        if WINDOWS and ctypes:
            LD = 0x0002; LU = 0x0004; RD = 0x0008; RU = 0x0010
            df, uf = (RD, RU) if button == "right" else (LD, LU)
            for _ in range(count):
                ctypes.windll.user32.mouse_event(df, 0, 0, 0, 0)
                time.sleep(0.04)
                ctypes.windll.user32.mouse_event(uf, 0, 0, 0, 0)
                time.sleep(0.04)

    def _mouse_scroll(self, x: int, y: int, delta: int = 3) -> None:
        self._mouse_move(x, y)
        if WINDOWS and ctypes:
            ctypes.windll.user32.mouse_event(0x0800, 0, 0, delta * 120, 0)

    def _send_keys(self, keys_str: str) -> None:
        if not WINDOWS or not keys_str or not ctypes:
            return
        VK = {
            "enter": 0x0D, "tab": 0x09, "esc": 0x1B, "space": 0x20,
            "backspace": 0x08, "delete": 0x2E, "home": 0x24, "end": 0x23,
            "pgup": 0x21, "pgdn": 0x22, "up": 0x26, "down": 0x28,
            "left": 0x25, "right": 0x27, "ctrl": 0x11, "alt": 0x12,
            "shift": 0x10, "win": 0x5B,
            **{f"f{i}": 0x6F + i for i in range(1, 13)},
        }
        keys    = [k.strip().lower() for k in keys_str.split("+") if k.strip()]
        pressed = []
        for k in keys:
            vk = VK.get(k)
            if vk is None and len(k) == 1:
                vk = ctypes.windll.user32.VkKeyScanW(ord(k)) & 0xFF
            if vk:
                ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
                pressed.append(vk)
        for vk in reversed(pressed):
            ctypes.windll.user32.keybd_event(vk, 0, 0x0002, 0)

    def _type_text(self, text: str) -> None:
        if not WINDOWS or not ctypes:
            return
        for ch in text:
            vk    = ctypes.windll.user32.VkKeyScanW(ord(ch))
            code  = vk & 0xFF
            shift = (vk >> 8) & 0xFF
            if shift & 1:
                ctypes.windll.user32.keybd_event(0x10, 0, 0, 0)
            ctypes.windll.user32.keybd_event(code, 0, 0, 0)
            ctypes.windll.user32.keybd_event(code, 0, 0x0002, 0)
            if shift & 1:
                ctypes.windll.user32.keybd_event(0x10, 0, 0x0002, 0)
            time.sleep(0.02)

    def _focus_window(self, title: str, partial: bool = True) -> None:
        """Amene une fenetre au premier plan par titre (exact ou partiel)."""
        if not WINDOWS or not title or not ctypes:
            return
        hwnd = ctypes.windll.user32.FindWindowW(None, title)
        if not hwnd and partial:
            found    = ctypes.c_size_t(0)
            EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool,
                                           ctypes.c_size_t, ctypes.c_size_t)
            def _cb(h, _):
                if ctypes.windll.user32.IsWindowVisible(h):
                    length = ctypes.windll.user32.GetWindowTextLengthW(h)
                    buf    = ctypes.create_unicode_buffer(length + 1)
                    ctypes.windll.user32.GetWindowTextW(h, buf, length + 1)
                    if title.lower() in buf.value.lower():
                        found.value = h
                        return False
                return True
            ctypes.windll.user32.EnumWindows(EnumProc(_cb), 0)
            hwnd = found.value
        if hwnd:
            # SW_RESTORE (9) uniquement si la fenetre est minimisee,
            # pour eviter de changer taille/position si elle est deja visible
            if ctypes.windll.user32.IsIconic(hwnd):
                ctypes.windll.user32.ShowWindow(hwnd, 9)   # SW_RESTORE
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            time.sleep(0.15)

    # ── Detection d'ecran ─────────────────────
    def _check_screen_image(self, p: dict, single_shot: bool = False) -> bool:
        """Detection d'image en 2 passes, 100 % C-level PIL, sans boucle Python
        sur les pixels.

        Passe 1 — Thumbnail RGB ≤ 16 px : redimensionne template ET écran au même
                   facteur, glisse avec pas=4 px en espace thumbnail (~3 000 positions).
                   Score : SAD couleur via histogramme PIL (768 itérations Python max
                   par position). Retourne les 15 meilleures zones.
                   → Fonctionne sur fonds unis ET sur images structurées car compare
                     la RÉPARTITION SPATIALE DES COULEURS, pas uniquement les contours.

        Passe 2 — SAD niveaux de gris plein écran autour des 15 zones, pas=min/8.
                   Score précis sur le template entier. Retourne position + score final.
        """
        if not PIL_AVAILABLE or not Image or not ImageGrab or not ImageChops:
            return False
        template_b64 = p.get("template_b64", "")
        if not template_b64:
            return False
        threshold = float(p.get("threshold", 0.85))
        region    = p.get("region")

        import io, base64

        def _sad_rgb(a, b):
            """SAD moyen par pixel par canal [0..255], C-level PIL."""
            h = ImageChops.difference(a, b).histogram()  # 768 vals (R,G,B)
            n = (a.size[0] * a.size[1]) or 1
            return sum((i % 256) * h[i] for i in range(768)) / (n * 3)

        def _sad_gray(a, b):
            """SAD moyen par pixel [0..255], C-level PIL."""
            h = ImageChops.difference(a, b).histogram()  # 256 vals
            n = (a.size[0] * a.size[1]) or 1
            return sum(i * c for i, c in enumerate(h)) / n

        try:
            # ── Charger le template ───────────────────────────────────
            tmpl_rgb = Image.open(
                io.BytesIO(base64.b64decode(template_b64))).convert("RGB")
            tw, th = tmpl_rgb.size
            if tw < 4 or th < 4:
                return False

            # Mise à l'échelle résolution enregistrée → actuelle
            if self._sx != 1.0 or self._sy != 1.0:
                tw = max(4, round(tw * self._sx))
                th = max(4, round(th * self._sy))
                tmpl_rgb = tmpl_rgb.resize((tw, th), Image.BILINEAR)

            tmpl_gray = tmpl_rgb.convert("L")

            # ── Thumbnail passe 1 (≤16 px sur le grand côté) ─────────
            THUMB  = 16
            s      = THUMB / max(tw, th)
            tw_t   = max(2, round(tw * s))
            th_t   = max(2, round(th * s))
            tmpl_t = tmpl_rgb.resize((tw_t, th_t), Image.BOX)

            # ── Origine région ────────────────────────────────────────
            ox, oy = (self._sc(int(region[0]), int(region[1]))
                      if region else (0, 0))

            STEP_T  = 4    # pas dans l'espace thumbnail
            TOP_N   = 15   # candidats transmis à passe 2

            deadline   = time.time() + (0 if single_shot else 10)
            first_pass = True
            best_score = 0.0
            best_rx, best_ry = ox, oy

            while first_pass or time.time() < deadline:
                first_pass = False
                if self._stop:
                    return False

                bbox = None
                if region:
                    x2, y2 = self._sc(int(region[2]), int(region[3]))
                    bbox   = (ox, oy, x2, y2)

                screen_rgb  = ImageGrab.grab(bbox=bbox).convert("RGB")
                screen_gray = screen_rgb.convert("L")
                sw, sh      = screen_rgb.size
                if sw < tw or sh < th:
                    time.sleep(0.1)
                    continue

                # ── Passe 1 : thumbnail RGB ───────────────────────────
                scr_t_w = max(tw_t + 1, round(sw * s))
                scr_t_h = max(th_t + 1, round(sh * s))
                scr_t   = screen_rgb.resize((scr_t_w, scr_t_h), Image.BOX)

                cands = []
                for cy in range(0, scr_t_h - th_t + 1, STEP_T):
                    for cx in range(0, scr_t_w - tw_t + 1, STEP_T):
                        crop_t  = scr_t.crop((cx, cy, cx + tw_t, cy + th_t))
                        sad_val = _sad_rgb(crop_t, tmpl_t)
                        score_t = 1.0 - sad_val / 255.0
                        # Coordonnées dans l'espace plein écran (relatif au bbox)
                        fx = min(sw - tw, max(0, round(cx / s)))
                        fy = min(sh - th, max(0, round(cy / s)))
                        cands.append((score_t, fx, fy))

                cands.sort(reverse=True)

                # ── Passe 2 : SAD pleine résolution, pas grossier ─────
                # Marge couvre l'incertitude du pas thumbnail + zone tampon
                margin = round(STEP_T / s) + max(tw // 8, th // 8)
                step2  = max(2, min(tw, th) // 8)

                iter_best = 0.0
                iter_rx   = ox
                iter_ry   = oy

                seen = set()   # evite de re-scanner zones deja couvertes
                for _, cand_x, cand_y in cands[:TOP_N]:
                    if self._stop:
                        return False
                    x0 = max(0,       cand_x - margin)
                    y0 = max(0,       cand_y - margin)
                    x1 = min(sw - tw, cand_x + margin)
                    y1 = min(sh - th, cand_y + margin)
                    zone_key = (x0 // max(margin, 1), y0 // max(margin, 1))
                    if zone_key in seen:
                        continue
                    seen.add(zone_key)

                    for fy2 in range(y0, y1 + 1, step2):
                        for fx2 in range(x0, x1 + 1, step2):
                            crop  = screen_gray.crop((fx2, fy2, fx2 + tw, fy2 + th))
                            score = 1.0 - _sad_gray(crop, tmpl_gray) / 255.0
                            if score > iter_best:
                                iter_best = score
                                iter_rx   = fx2
                                iter_ry   = fy2

                # ── Passe 3 : raffinement pixel-précis ────────────────
                # Fenêtre ±step2 autour du meilleur candidat P2, pas = 1 px
                p3x0 = max(0,       iter_rx - step2)
                p3y0 = max(0,       iter_ry - step2)
                p3x1 = min(sw - tw, iter_rx + step2)
                p3y1 = min(sh - th, iter_ry + step2)
                for fy3 in range(p3y0, p3y1 + 1):
                    for fx3 in range(p3x0, p3x1 + 1):
                        crop  = screen_gray.crop((fx3, fy3, fx3 + tw, fy3 + th))
                        score = 1.0 - _sad_gray(crop, tmpl_gray) / 255.0
                        if score > iter_best:
                            iter_best = score
                            iter_rx   = fx3
                            iter_ry   = fy3

                best_score = iter_best
                best_rx    = ox + iter_rx
                best_ry    = oy + iter_ry

                if best_score >= threshold:
                    self._show_debug_overlay(best_rx, best_ry, tw, th, best_score)
                    return True

                if single_shot:
                    self._show_debug_overlay(best_rx, best_ry, tw, th, best_score)
                    break

                self._show_debug_overlay(best_rx, best_ry, tw, th, best_score)
                time.sleep(0.15)

        except Exception:
            pass
        return False

    def _show_debug_overlay(self, x: int, y: int, w: int, h: int, score: float) -> None:
        """Dessine un rectangle de debug autour de la zone detectee (GDI, 2 s).
        Actif uniquement si self._debug_overlay est True.
        Vert  = trouve (score >= 0.85),  Orange = presque,  Rouge = loin.
        """
        if not self._debug_overlay:
            return
        if not WINDOWS or ctypes is None:
            return
        import threading
        def _run():
            try:
                user32 = ctypes.windll.user32
                gdi32  = ctypes.windll.gdi32
                # Couleur en fonction du score (BGR pour GDI)
                if score >= 0.85:
                    bgr = 0x00CC00        # vert
                elif score >= 0.60:
                    bgr = 0x0099FF        # orange
                else:
                    bgr = 0x3C3CFF        # rouge
                label = f"Score: {score:.3f}"
                end = time.time() + 2.0
                while time.time() < end:
                    dc = user32.GetDC(0)
                    # Rectangle
                    pen      = gdi32.CreatePen(0, 3, bgr)        # PS_SOLID
                    old_pen  = gdi32.SelectObject(dc, pen)
                    null_br  = gdi32.GetStockObject(5)           # NULL_BRUSH
                    old_br   = gdi32.SelectObject(dc, null_br)
                    gdi32.Rectangle(dc, x, y, x + w, y + h)
                    gdi32.SelectObject(dc, old_pen)
                    gdi32.SelectObject(dc, old_br)
                    gdi32.DeleteObject(pen)
                    # Label score
                    gdi32.SetBkMode(dc, 1)           # TRANSPARENT
                    gdi32.SetTextColor(dc, bgr)
                    user32.DrawTextW(dc, label, len(label),
                                     ctypes.byref(ctypes.wintypes.RECT(x, max(0, y - 20),
                                                                        x + 160, y)),
                                     0x0025)          # DT_LEFT|DT_SINGLELINE|DT_VCENTER
                    user32.ReleaseDC(0, dc)
                    time.sleep(0.05)
            except Exception:
                pass
        threading.Thread(target=_run, daemon=True).start()

    def _check_pixel_color(self, p: dict) -> bool:
        if not PIL_AVAILABLE or not ImageGrab:
            return False
        x, y  = self._sc(int(p.get("x", 0)), int(p.get("y", 0)))
        r, g, b = int(p.get("r", 0)), int(p.get("g", 0)), int(p.get("b", 0))
        tol   = int(p.get("tolerance", 10))
        try:
            px = ImageGrab.grab(bbox=(x, y, x + 1, y + 1)).getpixel((0, 0))
            return (abs(px[0] - r) <= tol and
                    abs(px[1] - g) <= tol and
                    abs(px[2] - b) <= tol)
        except Exception:
            return False
