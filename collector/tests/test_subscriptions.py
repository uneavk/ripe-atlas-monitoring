import unittest
from app.telegram_subscriptions import command

class CommandsTests(unittest.TestCase):
    def update(self,text,kind='private'):
        return {'update_id':1,'message':{'text':text,'chat':{'id':123,'type':kind},'from':{'id':123,'is_bot':False}}}
    def test_start_and_deep_link(self):
        self.assertEqual(command(self.update('/start')),(123,'/start'))
        self.assertEqual(command(self.update('/start@ripe_atlas_lab_bot source')),(123,'/start'))
    def test_stop_and_status(self):
        self.assertEqual(command(self.update('/stop')),(123,'/stop'))
        self.assertEqual(command(self.update('/status')),(123,'/status'))
    def test_ignore_groups_plain_text_and_unknown_updates(self):
        self.assertIsNone(command(self.update('/start','group')))
        self.assertIsNone(command(self.update('hello')))
        self.assertIsNone(command({'update_id':1}))
    def test_ignore_bot_and_mismatched_sender(self):
        u=self.update('/start');u['message']['from']['is_bot']=True
        self.assertIsNone(command(u))
        u=self.update('/start');u['message']['from']['id']=456
        self.assertIsNone(command(u))
