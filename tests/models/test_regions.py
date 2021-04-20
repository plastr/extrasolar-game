# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import math
from front.data import audio_regions
from front.tests import base
from front.lib import geometry
from front.models import region as region_module

class TestRegions(base.TestCase):
    def test_audio_region_radius(self):
        # Make sure that points just inside and outside of a region return correct values from
        # the point_inside function.  If this is failing, it is likely due to a failure to
        # convert between Leaflet's display coordinates and our canonical map coordinates.
        rgn = audio_regions.AudioRegion(region_id='RGN_TEST_01',
                        mission_definition='',
                        shape='CIRCLE',
                        verts= [],
                        center=[6.242774786597846, -109.41696166992186],
                        radius=99.4)

        self.assertEqual(rgn.point_inside(6.241732260824132, -109.41654324531555), False)
        self.assertEqual(rgn.point_inside(6.241918902419462, -109.41665321588516), True)

    def test_nested_triggers_and_zones(self):
        # Make sure that there is always at least a 51m gap between audio triggers and zones.
        def assert_nested_regions(audio_trigger_id, zone_id, min_distance):
            # This helper function computes the minimum distance between the edges of 2 nested circles.
            # and makes sure that they are nested with the boundaries no closer than min_distance.
            rgn_outer = audio_regions._get_region_by_id(audio_trigger_id)
            rgn_inner = region_module.from_id(zone_id)
            if rgn_outer.shape == 'CIRCLE' and rgn_inner.shape == 'CIRCLE':
                center_outer = geometry.lat_lng_to_meters(rgn_outer.center[0], rgn_outer.center[1])
                center_inner = geometry.lat_lng_to_meters(rgn_inner.center[0], rgn_inner.center[1])
                dx = center_outer[0] - center_inner[0]
                dy = center_outer[1] - center_inner[1]
                dist_between_centers = math.sqrt(dx*dx + dy*dy)
                dist_between_edges = rgn_outer.radius - rgn_inner.radius - dist_between_centers
                self.assertTrue(dist_between_edges > min_distance,
                    'Region boundaries too close for %s and %s [%.2f <= %.2f]' % (audio_trigger_id, zone_id, dist_between_edges, min_distance))
            elif rgn_outer.shape == 'POLYGON' and rgn_inner.shape == 'CIRCLE':
                self.assertTrue(geometry.point_inside_polygon(rgn_inner.center, rgn_outer.verts))
                # We need to convert our points to meters to get an accurate distance.
                verts_meters = [geometry.lat_lng_to_meters(v[0], v[1]) for v in rgn_outer.verts]
                center_meters = geometry.lat_lng_to_meters(rgn_inner.center[0], rgn_inner.center[1])
                dist_to_polygon = geometry.distance_to_polygon(center_meters, verts_meters) - rgn_inner.radius
                self.assertTrue(dist_to_polygon > min_distance,
                    'Region boundaries too close for %s and %s [%.2f <= %.2f]' % (audio_trigger_id, zone_id, dist_to_polygon, min_distance))
            else:
                self.assertTrue(0, 'Unexpected region shapes in assert_nested_regions.')

        assert_nested_regions('RGN_AUDIO_TUTORIAL01_TRIGGER', 'RGN_AUDIO_TUTORIAL01_ZONE', 50.5)
        assert_nested_regions('RGN_AUDIO_MYSTERY01_TRIGGER',  'RGN_AUDIO_MYSTERY01_ZONE',  50.5)
        assert_nested_regions('RGN_AUDIO_MYSTERY02_TRIGGER',  'RGN_AUDIO_MYSTERY02_ZONE',  50.5)
        assert_nested_regions('RGN_AUDIO_MYSTERY03_TRIGGER',  'RGN_AUDIO_MYSTERY03_ZONE',  50.5)
        assert_nested_regions('RGN_AUDIO_MYSTERY04_TRIGGER',  'RGN_AUDIO_MYSTERY04_ZONE',  50.5)
        assert_nested_regions('RGN_AUDIO_MYSTERY05_TRIGGER',  'RGN_AUDIO_MYSTERY05_ZONE',  50.5)
        assert_nested_regions('RGN_AUDIO_MYSTERY06_TRIGGER',  'RGN_AUDIO_MYSTERY06_ZONE',  50.5)
        assert_nested_regions('RGN_AUDIO_MYSTERY07_TRIGGER',  'RGN_AUDIO_MYSTERY07_ZONE',  50.5)

    def test_nested_zones_and_pinpoints(self):
        # Make sure that the distance between a zone edge and pinpoint is always less than the
        # accurate_id threshold.
        def assert_zone_and_pinpoint(zone_id, pinpoint_id, min_distance):
            # This helper function computes the minimum distance between the edges of 2 nested circles.
            # and makes sure that they are nested with the boundaries no closer than min_distance.
            zone     = region_module.from_id(zone_id)
            pinpoint = region_module.from_id(pinpoint_id)
            self.assertTrue(zone.shape == 'CIRCLE')
            self.assertTrue(zone.shape == 'CIRCLE' or zone.shape == 'POINT')
            center_zone     = geometry.lat_lng_to_meters(zone.center[0],     zone.center[1])
            center_pinpoint = geometry.lat_lng_to_meters(pinpoint.center[0], pinpoint.center[1])
            dx = center_zone[0] - center_pinpoint[0]
            dy = center_zone[1] - center_pinpoint[1]
            dist_between_centers = math.sqrt(dx*dx + dy*dy)
            dist_between_edges = zone.radius - dist_between_centers
            self.assertTrue(dist_between_edges > min_distance,
                'Pinpoint %s to close to zone %s [%.2f <= %.2f]' % (pinpoint_id, zone_id, dist_between_edges, min_distance))
        
        # For AUDIO_TUTORIAL01, we add the bristletongue's accurate_id_threshold to their territory radius.
        assert_zone_and_pinpoint('RGN_AUDIO_TUTORIAL01_ZONE', 'RGN_AUDIO_TUTORIAL01_PINPOINT', 20.0+8.0) 
        assert_zone_and_pinpoint('RGN_AUDIO_MYSTERY01_ZONE',  'RGN_AUDIO_MYSTERY01_PINPOINT',  20.0)
        assert_zone_and_pinpoint('RGN_AUDIO_MYSTERY02_ZONE',  'RGN_AUDIO_MYSTERY02_PINPOINT',  20.0)
        assert_zone_and_pinpoint('RGN_AUDIO_MYSTERY03_ZONE',  'RGN_AUDIO_MYSTERY03_PINPOINT',  20.0)
        assert_zone_and_pinpoint('RGN_AUDIO_MYSTERY04_ZONE',  'RGN_AUDIO_MYSTERY04_PINPOINT',  20.0)
        assert_zone_and_pinpoint('RGN_AUDIO_MYSTERY05_ZONE',  'RGN_AUDIO_MYSTERY05_PINPOINT',  20.0)
        assert_zone_and_pinpoint('RGN_AUDIO_MYSTERY06_ZONE',  'RGN_AUDIO_MYSTERY06_PINPOINT',  20.0)
        # Note: For AUDIO_MYSTERY07, we have many pinpoints, so this test may not make sense.
        
    def test_clockwise_regions(self):
        # TODO: Test all polygon regions for clockwise orientation.
        all_regions = region_module._get_all_region_definitions()
        for rgn_id, rgn in all_regions.iteritems():
            if rgn['shape'] == "POLYGON":
                # Take the midpoint of the first line segment and offset it slightly in the
                # direction that we would expect to be the interior for a clockwise-oriented
                # polygon.  Make sure it is, in fact, inside our polygon.
                p0 = rgn['verts'][0]
                p1 = rgn['verts'][1]
                dlat = p1[0] - p0[0];
                dlng = p1[1] - p0[1];
                self.assertTrue(dlat != 0.0 or dlng != 0.0)
                offset_midpoint = [(p0[0]+p1[0])*0.5 - dlng*0.1,
                                   (p0[1]+p1[1])*0.5 + dlat*0.1]
                self.assertTrue(geometry.point_inside_polygon(offset_midpoint, rgn['verts']),
                    'Region %s does not appear to have a clockwise vertex ordering.' % (rgn_id))
