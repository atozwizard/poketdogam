const test = require("node:test");
const assert = require("node:assert/strict");
const { analyzeRgba } = require("../app/ui/camera-quality.js");

function rgba(values) {
  return Uint8ClampedArray.from(values.flatMap((value) => [value, value, value, 255]));
}

test("camera quality rejects dark and overexposed frames", () => {
  assert.equal(analyzeRgba(rgba([20, 20, 20, 20])).state, "dark");
  assert.equal(analyzeRgba(rgba([240, 240, 240, 240])).state, "bright");
});

test("camera quality separates blurred and usable frames", () => {
  assert.equal(analyzeRgba(rgba([120, 121, 120, 121])).state, "blurred");
  assert.equal(analyzeRgba(rgba([70, 180, 70, 180])).state, "ready");
});
