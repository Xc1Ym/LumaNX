// LumaNX automatic controller semantics. No keyboard events or user bindings.
#pragma once
#import <GameController/GameController.h>

static inline uint64_t luma_face_buttons(GCExtendedGamepad *pad) {
    // Apple already exposes Nintendo pads by their printed letters: buttonA is
    // the right-hand A, not the bottom B. Xbox buttonA / PlayStation cross also
    // become game A under LumaNX's label policy. Never swap a second time based
    // on the controller name or HID product category.
    uint64_t bits = 0;
    if (pad.buttonA.isPressed) bits |= 1ull << 0;
    if (pad.buttonB.isPressed) bits |= 1ull << 1;
    if (pad.buttonX.isPressed) bits |= 1ull << 2;
    if (pad.buttonY.isPressed) bits |= 1ull << 3;
    return bits;  // Switch ABI: A=0, B=1, X=2, Y=3, shared by Mac and iOS.
}
