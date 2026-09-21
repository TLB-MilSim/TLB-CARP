/* generated from calibration/test-vectors.json; do not hand edit */
createHashMapFromArray [
    ["schemaVersion", 1],
    ["vectors", [createHashMapFromArray [
          ["id", "c17-flat-3000m-500kph-zero"],
          ["aircraft", "c17"],
          ["mode", "TOUCHDOWN"],
          ["actionAltitudeAslM", 3000],
          ["openingTerrainAslM", 0],
          ["dzTerrainAslM", 0],
          ["groundSpeedMs", 138.8888889],
          ["verticalSpeedMs", 0],
          ["runInDeg", 270],
          ["windSpeedMs", 0],
          ["windFromDeg", 0],
          ["expected", createHashMapFromArray [
              ["totalAlongM", 3537.96],
              ["totalRightM", -51.3],
              ["predictedChuteAglM", 290.79],
              ["predictedCanopyTimeS", 24.55]
          ]]
      ], createHashMapFromArray [
          ["id", "c17-flat-3000m-500kph-crosswind5"],
          ["aircraft", "c17"],
          ["mode", "TOUCHDOWN"],
          ["actionAltitudeAslM", 3000],
          ["openingTerrainAslM", 0],
          ["dzTerrainAslM", 0],
          ["groundSpeedMs", 138.8888889],
          ["verticalSpeedMs", 0],
          ["runInDeg", 270],
          ["windSpeedMs", 5],
          ["windFromDeg", 180],
          ["expected", createHashMapFromArray [
              ["totalAlongM", 3537.96],
              ["totalRightM", 50.58],
              ["predictedChuteAglM", 290.79],
              ["predictedCanopyTimeS", 24.55]
          ]]
      ], createHashMapFromArray [
          ["id", "c17-run5-plus5-crosswind"],
          ["aircraft", "c17"],
          ["mode", "TOUCHDOWN"],
          ["actionAltitudeAslM", 2985.888],
          ["openingTerrainAslM", 25.334],
          ["dzTerrainAslM", 1.445],
          ["groundSpeedMs", 137.586],
          ["verticalSpeedMs", -0.744],
          ["runInDeg", 270.6576],
          ["windSpeedMs", 5],
          ["windFromDeg", 180],
          ["expected", createHashMapFromArray [
              ["totalAlongM", 3473.87],
              ["totalRightM", 78.39],
              ["predictedCanopyTimeS", 30.13]
          ]]
      ], createHashMapFromArray [
          ["id", "c17-run6-minus5-crosswind"],
          ["aircraft", "c17"],
          ["mode", "TOUCHDOWN"],
          ["actionAltitudeAslM", 2949.588],
          ["openingTerrainAslM", 45.36],
          ["dzTerrainAslM", 59.374],
          ["groundSpeedMs", 142.201],
          ["verticalSpeedMs", -1.904],
          ["runInDeg", 266.496],
          ["windSpeedMs", 5],
          ["windFromDeg", 0],
          ["expected", createHashMapFromArray [
              ["totalAlongM", 3534.92],
              ["totalRightM", -136.99],
              ["predictedCanopyTimeS", 21.33]
          ]]
      ]]]
]
