// Shared Mac/iOS native face-button policy, independent of DM_INPUT_CONFIG.
#pragma once
#import <Foundation/Foundation.h>
#import <GameController/GameController.h>
#include <stdint.h>
#include <stdlib.h>

static inline NSString *luma_controller_key(GCController *controller) {
    NSString *vendor = controller.vendorName ?: @"";
    NSString *category = controller.productCategory ?: @"";
    if (!vendor.length && !category.length) return nil;
    return [NSString stringWithFormat:@"%lu:%@%lu:%@",
        (unsigned long)[vendor lengthOfBytesUsingEncoding:NSUTF8StringEncoding], vendor,
        (unsigned long)[category lengthOfBytesUsingEncoding:NSUTF8StringEncoding], category];
}
static inline NSDictionary *luma_parse_controller_layouts(NSData *data) {
    if (!data) return @{};
    id object = [NSJSONSerialization JSONObjectWithData:data options:0 error:NULL];
    if (![object isKindOfClass:NSDictionary.class] || ![object[@"schema"] isEqual:@1] ||
        ![object[@"layouts"] isKindOfClass:NSDictionary.class]) return @{};
    return object[@"layouts"];
}
static inline NSDictionary *luma_controller_layouts(void) {
    // Read once per process. UI changes apply on the next launch; player slots
    // and reconnects always resolve against the controller's reported identity.
    static NSDictionary *layouts;
    static dispatch_once_t once;
    dispatch_once(&once, ^{
        const char *path = getenv("DM_CONTROLLER_LAYOUTS");
        NSData *data = path ? [NSData dataWithContentsOfFile:[NSString stringWithUTF8String:path]] : nil;
        layouts = luma_parse_controller_layouts(data);
    });
    return layouts;
}
static inline uint64_t luma_face_buttons(GCExtendedGamepad *pad) {
    NSString *key = luma_controller_key(pad.controller);
    BOOL swap = key && [luma_controller_layouts()[key] isEqual:@"switchPosition"];
    // Default: Nintendo printed letters, Xbox letters, PS cross/circle/square/
    // triangle -> A/B/X/Y. Physical Switch mode is explicit; never guess by name.
    uint64_t bits = 0;
    if (pad.buttonA.isPressed) bits |= 1ull << (swap ? 1 : 0);
    if (pad.buttonB.isPressed) bits |= 1ull << (swap ? 0 : 1);
    if (pad.buttonX.isPressed) bits |= 1ull << (swap ? 3 : 2);
    if (pad.buttonY.isPressed) bits |= 1ull << (swap ? 2 : 3);
    return bits;  // Switch ABI: A=0, B=1, X=2, Y=3, shared by Mac and iOS.
}
