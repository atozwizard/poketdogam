const test = require("node:test");
const assert = require("node:assert/strict");
const { analyzeRgba, nameBandCropBox } = require("../app/ui/camera-quality.js");

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

test("name band crop targets the upper card-title region", () => {
  const box = nameBandCropBox(1000, 620);
  assert.equal(box.left, 100);
  assert.equal(box.top, 50);
  assert.equal(box.width, 800);
  assert.equal(box.height, 112);
});
