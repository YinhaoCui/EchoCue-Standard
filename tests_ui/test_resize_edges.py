"""Reproduce edge resizing with the saved narrow-panel layout from the report."""
import unittest
import test_listen_page as listen


@unittest.skipIf(listen.sync_playwright is None, 'playwright is not installed')
class ResizeEdgesTests(unittest.TestCase):
    theme = 'midnight'
    setUpClass = classmethod(listen.ListenPageTests.setUpClass.__func__)
    tearDownClass = classmethod(listen.ListenPageTests.tearDownClass.__func__)
    setUp = listen.ListenPageTests.setUp
    tearDown = listen.ListenPageTests.tearDown
    drag = listen.ListenPageTests.drag

    def reported_layout(self):
        with self.bridge.lock:
            self.bridge.state['options'].update(listen_layout='0,0,650,380,400', midnight_split='60')
            self.bridge.publish()
        self.page.wait_for_function("current.options.midnight_split === '60'")

    def test_saved_panel_widths_do_not_leave_a_large_gap_between_columns(self):
        self.reported_layout()
        left = self.page.locator('.transcript-panel').bounding_box()
        right = self.page.locator('.answer-panel').bounding_box()
        self.assertAlmostEqual(right['x'] - left['x'] - left['width'], 12, delta=1)

    def test_dragging_either_shared_edge_moves_one_divider(self):
        before = self.page.locator('.transcript-panel').bounding_box()['width']
        self.drag('.side-grip[data-panel="1"][data-edge="right"]', 60, 0)
        after = self.page.locator('.transcript-panel').bounding_box()
        answer = self.page.locator('.answer-panel').bounding_box()
        self.assertAlmostEqual(after['width'], before + 60, delta=3)
        self.assertAlmostEqual(answer['x'] - after['x'] - after['width'], 12, delta=1)

    def test_all_outer_window_edges_have_resize_targets(self):
        for edge in ('left', 'right', 'top', 'bottom', 'top-left', 'top-right', 'bottom-left', 'bottom-right'):
            self.assertEqual(self.page.locator('[data-resize-edge="' + edge + '"]').count(), 1, edge)

    def test_outer_edges_delegate_to_native_resize(self):
        self.page.evaluate("window.__rects=[];window.pywebview={api:{bounds:()=>Promise.resolve({width:1180,height:840,left:80,top:50}),resize:(...rect)=>{window.__rects.push(rect);return Promise.resolve(true)}}}")
        edges=('left','right','top','bottom','top-left','top-right','bottom-left','bottom-right')
        expected=([1175,840,85,50],[1185,840],[1180,835,80,55],[1180,845],
                  [1175,835,85,55],[1185,835,80,55],[1175,845,85,50],[1185,845])
        for edge,rect in zip(edges,expected):
            self.drag('[data-resize-edge="' + edge + '"]', 5, 5)
            self.page.wait_for_function('rect => JSON.stringify(window.__rects.at(-1)) === JSON.stringify(rect)',arg=rect)

    def test_outer_panel_edges_delegate_to_window_without_creating_gaps(self):
        self.page.evaluate("window.__rects=[];window.pywebview={api:{bounds:()=>Promise.resolve({width:1180,height:840,left:80,top:50}),resize:(...rect)=>{window.__rects.push(rect);return Promise.resolve(true)}}}")
        self.drag('.side-grip[data-panel="1"][data-edge="left"]', 10, 0)
        self.page.wait_for_function('JSON.stringify(window.__rects.at(-1)) === JSON.stringify([1170,840,90,50])')
        self.drag('.side-grip[data-panel="2"][data-edge="right"]', 10, 0)
        self.page.wait_for_function('JSON.stringify(window.__rects.at(-1)) === JSON.stringify([1190,840])')
        left=self.page.locator('.transcript-panel').bounding_box()
        right=self.page.locator('.answer-panel').bounding_box()
        self.assertAlmostEqual(right['x']-left['x']-left['width'],12,delta=1)

    def test_outer_targets_follow_the_visible_frame_instead_of_empty_margins(self):
        frame=self.page.evaluate('windowFrame()')
        for edge in ('left','right','top','bottom'):
            target=self.page.locator('[data-resize-edge="'+edge+'"]').bounding_box()
            position={'left':target['x'],'right':target['x']+target['width'],
                      'top':target['y'],'bottom':target['y']+target['height']}[edge]
            self.assertAlmostEqual(position,frame[edge],delta=1)
