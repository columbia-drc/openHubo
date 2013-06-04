from openravepy import *
from numpy import *
import openhubo
import sys
import time
import unittest
import servo
import threading

class TestServoCommands(unittest.TestCase):
    def setUp(self):

        (env,options)=openhubo.setup()
        env.SetDebugLevel(2)
        #NOTE: Loads trajectory controller, which passes servo commands down
        options.physicsfile='physics.xml'
        options.scenefile=None
        [self.robot,self.controller,self.ind,__,__]=openhubo.load(env,options)
        env.GetPhysicsEngine().SetGravity([0,0,0])
        self.env=env
        self.pose=zeros(self.robot.GetDOF())
        self.env.StartSimulation(0.0005)

    def tearDown(self):
        self.env.Destroy()
    
    def test_pose(self):
        pose=self.pose
        pose[self.ind('RSR')]=-22.5*pi/180
        pose[self.ind('LSR')]=22.5*pi/180
        self.assertTrue(self.controller.SetDesired(pose))

    def test_setgains(self):
        self.assertTrue(self.controller.SendCommand('set gains 50 0 7'))

    def test_degrees(self):
        self.assertTrue(self.controller.SendCommand('set degrees '))
        self.assertEqual(self.controller.SendCommand('get units '),'degrees')

        self.controller.SendCommand('set pos1 {} {} '.format(self.ind('LSP'),-10))
        time.sleep(5)
        theta=float(self.controller.SendCommand('get pos1 {}'.format(self.ind('LSP'))))
        self.assertLess(abs(theta+10),1)

    def test_radians(self):
        self.assertTrue(self.controller.SendCommand('set radians '))
        self.assertEqual(self.controller.SendCommand('get units '),'radians')

        self.controller.SendCommand('set pos1 {} {} '.format(self.ind('LSP'),-pi/4))
        time.sleep(5)
        theta=self.controller.SendCommand('get pos1 {} '.format(self.ind('LSP')))
        self.assertLess(abs(float(theta)+pi/4),.1)

if __name__=='__main__':
    unittest.main(verbosity=2,testRunner=unittest.TextTestRunner())