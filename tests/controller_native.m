// Exercise the actual nxnative Mac front end with Apple's writable snapshots.
#include "front_mac.m"
#include <assert.h>
#include <time.h>
#import <objc/runtime.h>

// Only replace device discovery, never the production input or slot logic.
static NSArray<GCController *> *testControllers;
@interface GCController (LayoutDiscovery)
+ (NSArray<GCController *> *)luma_testControllers;
@end
@implementation GCController (LayoutDiscovery)
+ (NSArray<GCController *> *)luma_testControllers { return testControllers ?: @[]; }
@end

int g_swkbd_min_chars;
static uint64_t received[DM_PLAYERS];
static int32_t axes[DM_PLAYERS][4];
void dm_input_set(uint64_t b, int32_t x, int32_t y, int32_t z, int32_t w) {(void)b;(void)x;(void)y;(void)z;(void)w;}
void dm_pad_set_player(int p,uint64_t b,int32_t x,int32_t y,int32_t z,int32_t w) {received[p]=b;axes[p][0]=x;axes[p][1]=y;axes[p][2]=z;axes[p][3]=w;}
void dm_pad_set(uint64_t b,int32_t x,int32_t y,int32_t z,int32_t w) {dm_pad_set_player(0,b,x,y,z,w);}
void dm_pad_players(uint32_t mask) {(void)mask;}
uint32_t dm_player_npad(int p) {return (uint32_t)p;}
// The controller applet queries HID service state. This input-only harness
// never opens that prompt; fail if it unexpectedly reaches the service.
int dm_players_reported(void) {abort();}
void dm_touch_set(const dm_touch *t,int n) {(void)t;(void)n;}
void dm_focus_set(int s) {(void)s;}
void dm_audio_suspend(int s) {(void)s;}
void dm_gfx_suspend(int s) {(void)s;}
void dm_haptics_apple_init(void) {}
void dm_haptics_apple_controller(int p,GCController *c) {(void)p;(void)c;}
void dm_haptics_apple_shutdown(void) {}
// The front end now includes the cheats UI. This input-only harness never opens
// it; fail if it reaches those services instead of loading any player state.
// The engine's t_cheats suite exercises the real implementation separately.
int dm_cheats_found(void) {abort();}
int dm_cheats_ncheats(void) {abort();}
const char *dm_cheats_build(void) {abort();}
const char *dm_cheats_dir_path(void) {abort();}
int dm_cheats_nothers(void) {abort();}
const char *dm_cheats_other(int i) {(void)i;abort();}
const char *dm_cheat_name_at(int i) {(void)i;abort();}
const char *dm_cheat_why_at(int i) {(void)i;abort();}
int dm_cheat_kind_at(int i) {(void)i;abort();}
int dm_cheat_on_at(int i) {(void)i;abort();}
void dm_cheat_toggle(int i) {(void)i;abort();}
void dm_cheats_reload(void) {abort();}
int dm_cheat_flags_at(int i) {(void)i;abort();}
const char *dm_cheat_section_at(int i) {(void)i;abort();}
const char *dm_cheat_note_at(int i) {(void)i;abort();}
const char *dm_cheat_type_at(int i) {(void)i;abort();}
int dm_cheat_preview(int i,char *out,size_t cap) {(void)i;(void)out;(void)cap;abort();}
int dm_cheat_value_get(int i,char *out,size_t cap) {(void)i;(void)out;(void)cap;abort();}
int dm_cheat_value_set(int i,const char *text) {(void)i;(void)text;abort();}
const char *dm_cheat_value_bounds(int i) {(void)i;abort();}
int dm_cheats_master(void) {abort();}
void dm_cheats_master_set(int on) {(void)on;abort();}
int dm_cheats_safe(void) {abort();}
void dm_cheats_safe_restore(void) {abort();}
const char *dm_cheats_report(void) {abort();}
const char *dm_cheats_version(void) {abort();}
const char *dm_cheats_other_version(int i) {(void)i;abort();}
int dm_cheats_nskipped(void) {abort();}
const char *dm_cheats_skipped_name(int i) {(void)i;abort();}
const char *dm_cheats_skipped_why(int i) {(void)i;abort();}
int dm_cheats_nsources(void) {abort();}
const char *dm_cheats_source(int i) {(void)i;abort();}
// The front end now publishes GameController and passive HID motion to the
// service layer. Keep those sinks in the harness, like the pad/haptics sinks
// above; the host's own tests cover sensor fusion and HID packet decoding.
void dm_motion_set(int p,const float acc[3],const float rot[3]) {(void)p;(void)acc;(void)rot;}
void dm_motion_set_hid(int p,const float acc[3],const float rot[3],uint64_t ns) {(void)p;(void)acc;(void)rot;(void)ns;}
static unsigned motion_clears[DM_PLAYERS], hid_motion_clears[DM_PLAYERS];
void dm_motion_clear(int p) {assert(p>=0&&p<DM_PLAYERS);motion_clears[p]++;}
void dm_motion_clear_hid(int p) {assert(p>=0&&p<DM_PLAYERS);hid_motion_clears[p]++;}
uint64_t now_ns(void) {
    struct timespec t;assert(clock_gettime(CLOCK_MONOTONIC_RAW,&t)==0);
    return (uint64_t)t.tv_sec*1000000000ull+(uint64_t)t.tv_nsec;
}

// Snapshot controllers have no product identity. Override identity only; keep
// Apple's real GCExtendedGamepad elements and the production pad_read path.
@interface NamedController : GCController
@property NSString *testName;
@property NSString *testCategory;
@property GCExtendedGamepad *testPad;
@end
@implementation NamedController
- (NSString *)vendorName {return self.testName;}
- (NSString *)productCategory {return self.testCategory;}
- (GCExtendedGamepad *)extendedGamepad {return self.testPad;}
@end

@interface IdentityPad : GCExtendedGamepad
@property GCController *identity;
@property GCExtendedGamepad *backing;
@end
@implementation IdentityPad
- (GCController *)controller {return self.identity;}
- (GCControllerButtonInput *)buttonA {return self.backing.buttonA;}
- (GCControllerButtonInput *)buttonB {return self.backing.buttonB;}
- (GCControllerButtonInput *)buttonX {return self.backing.buttonX;}
- (GCControllerButtonInput *)buttonY {return self.backing.buttonY;}
- (GCControllerButtonInput *)buttonMenu {return self.backing.buttonMenu;}
- (GCControllerButtonInput *)buttonOptions {return self.backing.buttonOptions;}
- (GCControllerButtonInput *)leftShoulder {return self.backing.leftShoulder;}
- (GCControllerButtonInput *)rightShoulder {return self.backing.rightShoulder;}
- (GCControllerButtonInput *)leftTrigger {return self.backing.leftTrigger;}
- (GCControllerButtonInput *)rightTrigger {return self.backing.rightTrigger;}
- (GCControllerButtonInput *)leftThumbstickButton {return self.backing.leftThumbstickButton;}
- (GCControllerButtonInput *)rightThumbstickButton {return self.backing.rightThumbstickButton;}
- (GCControllerDirectionPad *)dpad {return self.backing.dpad;}
- (GCControllerDirectionPad *)leftThumbstick {return self.backing.leftThumbstick;}
- (GCControllerDirectionPad *)rightThumbstick {return self.backing.rightThumbstick;}
@end

int main(void) {
    @autoreleasepool {
        GCController *snapshot=[GCController controllerWithExtendedGamepad];
        NamedController *c=[NamedController new];
        IdentityPad *pad=[IdentityPad new];pad.identity=c;pad.backing=snapshot.extendedGamepad;c.testPad=pad;
        NSString *layoutPath=[NSTemporaryDirectory() stringByAppendingPathComponent:NSUUID.UUID.UUIDString];
        c.testName=@"8BitDo 布局测试";c.testCategory=@"HID";
        NSString *physicalKey=luma_controller_key(c);
        assert([physicalKey isEqualToString:@"19:8BitDo 布局测试3:HID"]);
        NSDictionary *config=@{@"schema":@1,@"layouts":@{physicalKey:@"switchPosition",@"7:Unknown3:HID":@"future-mode"}};
        NSData *data=[NSJSONSerialization dataWithJSONObject:config options:0 error:NULL];
        assert([data writeToFile:layoutPath atomically:YES]);
        setenv("DM_CONTROLLER_LAYOUTS",layoutPath.UTF8String,1);
        for (NSString *bad in @[@"[]",@"null",@"{}",@"{\"schema\":2,\"layouts\":{}}",@"{\"schema\":1,\"layouts\":[]}",@"broken"]) {
            assert(luma_parse_controller_layouts([bad dataUsingEncoding:NSUTF8StringEncoding]).count==0);
        }
        int p=pad_slot_take(&g_slots,(__bridge const void *)c,"snapshot");assert(p==0);g_held[p]=c;
        GCControllerButtonInput *buttons[]={pad.buttonA,pad.buttonB,pad.buttonX,pad.buttonY};
        for (NSString *name in @[@"Nintendo Switch Pro Controller",@"Joy-Con (L/R)",@"Pro Controller",@"Xbox Wireless Controller",@"DualSense Wireless Controller",@"DualShock 4",@"Generic USB Controller"]) {
          for (NSString *category in @[@"HID",@"Switch Pro Controller",@"Nintendo Switch Joy-Con (L/R)"]) {
            c.testName=name;c.testCategory=category;
            // Nintendo's actual GameController ABI is label-based, as recorded
            // by upstream pad_apple.h (hardware-tested in nxnative PR #650).
            // The previous test incorrectly assumed buttonA meant physical B.
            uint64_t labels[]={DM_BTN_A,DM_BTN_B,DM_BTN_X,DM_BTN_Y};
            for(int i=0;i<4;i++) {
                [buttons[i] setValue:1];pad_read(pad);assert(received[p]==labels[i]);
                [buttons[i] setValue:0];pad_read(pad);assert(received[p]==0);
            }
          }
        }
        // Same model reconnects and different multiplayer slots use the same
        // exact-identity setting; another identity and a different mode do not.
        c.testName=@"8BitDo 布局测试";c.testCategory=@"HID";
        uint64_t physical[]={DM_BTN_B,DM_BTN_A,DM_BTN_Y,DM_BTN_X};
        for(int i=0;i<4;i++) {
            [buttons[i] setValue:1];pad_read(pad);assert(received[p]==physical[i]);
            [buttons[i] setValue:0];pad_read(pad);assert(received[p]==0);
        }
        NamedController *other=[NamedController new];other.testName=@"Other pad";other.testCategory=@"HID";
        IdentityPad *pad2=[IdentityPad new];pad2.identity=other;
        pad2.backing=[GCController controllerWithExtendedGamepad].extendedGamepad;other.testPad=pad2;
        int second=pad_slot_take(&g_slots,(__bridge const void *)other,"second");assert(second==1);g_held[second]=other;
        [pad.buttonA setValue:1];[pad2.buttonA setValue:1];pad_read(pad);pad_read(pad2);
        assert(received[p]==DM_BTN_B && received[second]==DM_BTN_A);
        Method discovery=class_getClassMethod(GCController.class,@selector(controllers));
        Method fixtureDiscovery=class_getClassMethod(GCController.class,@selector(luma_testControllers));
        method_exchangeImplementations(discovery,fixtureDiscovery);testControllers=@[other];
        pads_changed(c);assert(received[p]==0 && received[second]==DM_BTN_A);
        int reconnected=pad_slot_take(&g_slots,(__bridge const void *)c,"reconnected");assert(reconnected==0);g_held[reconnected]=c;
        pad_read(pad);assert(received[reconnected]==DM_BTN_B);
        c.testCategory=@"XInput";pad_read(pad);assert(received[reconnected]==DM_BTN_A);
        c.testName=@"Unknown";c.testCategory=@"HID";pad_read(pad);assert(received[reconnected]==DM_BTN_A);
        [pad.buttonA setValue:0];[pad2.buttonA setValue:0];pad_read(pad2);
        [[NSFileManager defaultManager] removeItemAtPath:layoutPath error:NULL];
        [pad.buttonA setValue:1];[pad.buttonB setValue:1];[pad.leftTrigger setValue:1];[pad.rightShoulder setValue:1];
        [pad.leftThumbstick setValueForXAxis:.75 yAxis:-.5];pad_read(pad);
        assert(received[p]==(DM_BTN_A|DM_BTN_B|DM_BTN_ZL|DM_BTN_R));assert(axes[p][0]>0&&axes[p][1]<0);
#if __has_include("motion_pro_mac.h")
        // Simulate an assigned passive motion source without opening HID devices.
        g_pro_player=p;
#endif
        input_release();assert(received[p]==0&&axes[p][0]==0);pad_read(pad);assert(received[p]==0);
#if __has_include("motion_pro_mac.h")
        assert(hid_motion_clears[p]>0);
#endif
        g_input_on=1;pad_read(pad);assert(received[p]&DM_BTN_A);
        pads_changed(c);assert(received[p]==0&&axes[p][0]==0);assert(g_held[p]==nil);
#if __has_include("motion_apple.h")
        assert(motion_clears[p]>0);
#endif
        method_exchangeImplementations(discovery,fixtureDiscovery);
        puts("PASS: native GameController face buttons, combos, axes, focus and disconnect cleanup");
    }
    return 0;
}
