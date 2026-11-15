import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from dashboards import build
from setup_metabase import layout

class DashboardContracts(unittest.TestCase):
    def test_panels_do_not_overlap(self):
        for dash in build():
            panels=layout(dash,[(s,{'id':n+1}) for n,s in enumerate(dash['cards'])])
            for i,a in enumerate(panels):
                self.assertLessEqual(a['col']+a['size_x'],24)
                for b in panels[i+1:]:
                    overlap=a['col']<b['col']+b['size_x'] and b['col']<a['col']+a['size_x'] and a['row']<b['row']+b['size_y'] and b['row']<a['row']+a['size_y']
                    self.assertFalse(overlap,(dash['key'],a['card_id'],b['card_id']))

    def test_native_filter_maps_to_the_own_question(self):
        for dash in build():
            specs=[(s,{'id':n+1}) for n,s in enumerate(dash['cards'])]
            for (spec,saved),panel in zip(specs,layout(dash,specs)):
                if spec['measurement']:
                    self.assertIn('{{measurement}}',spec['sql'])
                    self.assertEqual(panel['parameter_mappings'][0]['card_id'],saved['id'])
                    self.assertEqual(panel['parameter_mappings'][0]['target'],['variable',['template-tag','measurement']])
                else:self.assertFalse(panel['parameter_mappings'])

    def test_network_trends_keep_missing_intervals_null(self):
        for dash in build():
            for spec in dash['cards']:
                if 'CROSS JOIN analytics.measurement_directory' in spec['sql']:
                    self.assertIn('if(v.measurement_count=0,NULL,',spec['sql'])
                    self.assertEqual(spec['settings']['graph.missing_value'],'none')
                    self.assertTrue(all(s['line.missing']=='none' for s in spec['settings']['series_settings'].values()))

    def test_read_queries_do_not_expose_subscriber_tables(self):
        for dash in build():
            for spec in dash['cards']:
                self.assertTrue(spec['sql'].lstrip().upper().startswith(('SELECT','WITH')))
                self.assertNotIn('telegram_subscribers',spec['sql'])
                self.assertNotIn('chat_id',spec['sql'])

if __name__=='__main__':unittest.main()
