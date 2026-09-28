import unittest,json
from finance_proxy import local_links,request_payload,html_for_deck
class FinanceProxyTests(unittest.TestCase):
 def test_pattern_matching_tree_callback_keeps_grouped_node_inputs(self):
  nodes=[{'id':{'type':'mapa-no','id':'route|meta:12'},'property':'n_clicks','value':1},{'id':{'type':'mapa-no','id':'route|meta:13'},'property':'n_clicks','value':0}]
  data={'inputs':[nodes],'state':[{'id':'url','property':'pathname','value':'/finance/mapa'},{'id':'chosen','property':'data','value':{'property':'pathname','value':'/finance/private-value'}}],'changedPropIds':['{"id":"route|meta:12","type":"mapa-no"}.n_clicks']}
  got=json.loads(request_payload(json.dumps(data).encode()))
  self.assertEqual(got['inputs'],[nodes]);self.assertEqual(got['changedPropIds'],data['changedPropIds'])
  self.assertEqual(got['state'][0]['value'],'/mapa');self.assertEqual(got['state'][1],data['state'][1])
 def test_links_inside_deck_without_changing_external_maps(self):
  data={'props':{'href':'/planejamento','children':[{'src':'https://maps.example/map'},{'src':'/goal-image/a.jpg'}]}}
  got=local_links(data)
  self.assertEqual(got['props']['href'],'/finance/planejamento')
  self.assertEqual(got['props']['children'][0]['src'],'https://maps.example/map')
  self.assertEqual(got['props']['children'][1]['src'],'/finance/goal-image/a.jpg')
  self.assertEqual(data['props']['href'],'/planejamento')
 def test_route_callback_preserves_financial_values(self):
  data={'inputs':[{'id':'url','property':'pathname','value':'/finance/planejamento'},{'id':'amount','property':'value','value':123.45}],'state':[]}
  got=json.loads(request_payload(json.dumps(data).encode()))
  self.assertEqual(got['inputs'][0]['value'],'/planejamento');self.assertEqual(got['inputs'][1]['value'],123.45)
 def test_prefix_not_duplicated(self):self.assertEqual(local_links({'href':'/finance/planejamento'}),{'href':'/finance/planejamento'})
 def test_dash_escaped_slash_config(self):
  html='<script id="_dash-config" type="application/json">{"requests_pathname_prefix":"\\u002f"}</script><script src="/_dash/a.js"></script><a href="//cdn.example/x">a</a>'
  result=html_for_deck(html)
  self.assertIn('"requests_pathname_prefix": "/finance/"',result)
  self.assertIn('src="/finance/_dash/a.js"',result);self.assertIn('href="//cdn.example/x"',result)
if __name__=='__main__':unittest.main()
