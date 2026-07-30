(function exposeCameraQuality(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  root.PoketdogamCameraQuality = api;
})(typeof globalThis !== "undefined" ? globalThis : window, function cameraQualityFactory() {
  function analyzeRgba(pixels) {
    if (!pixels || pixels.length < 8 || pixels.length % 4 !== 0) {
      return {
        state: "unavailable",
        message: "카메라 화면을 확인하는 중입니다.",
        brightness: 0,
        edgeScore: 0,
      };
    }
    let luminanceTotal = 0;
    let edgeTotal = 0;
    let previous = 0;
    for (let index = 0; index < pixels.length; index += 4) {
      const luminance =
        0.2126 * pixels[index] + 0.7152 * pixels[index + 1] + 0.0722 * pixels[index + 2];
      luminanceTotal += luminance;
      if (index > 0) {
        edgeTotal += Math.abs(luminance - previous);
      }
      previous = luminance;
    }
    const sampleCount = pixels.length / 4;
    const brightness = luminanceTotal / sampleCount;
    const edgeScore = edgeTotal / Math.max(1, sampleCount - 1);
    if (brightness < 48) {
      return {
        state: "dark",
        message: "화면이 어둡습니다. 조명을 밝히고 다시 맞춰주세요.",
        brightness,
        edgeScore,
      };
    }
    if (brightness > 220) {
      return {
        state: "bright",
        message: "빛 반사가 강합니다. 카메라 각도를 조금 기울여주세요.",
        brightness,
        edgeScore,
      };
    }
    if (edgeScore < 5) {
      return {
        state: "blurred",
        message: "초점이 흐립니다. 대상을 가까이 두고 카메라를 고정하세요.",
        brightness,
        edgeScore,
      };
    }
    return {
      state: "ready",
      message: "밝기와 선명도가 좋습니다. 대상을 프레임의 70% 이상 채우고 촬영하세요.",
      brightness,
      edgeScore,
    };
  }

  return { analyzeRgba };
});
