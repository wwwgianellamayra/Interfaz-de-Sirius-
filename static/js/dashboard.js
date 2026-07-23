const $ = (id) => document.getElementById(id);

const stateMessages = {
  PRE_LAUNCH: "Verificación de sistemas y enlace RF",
  ASCENT: "Ascenso controlado hasta la altura de liberación",
  DESCENT_FREE: "Caída libre y monitoreo de altitud",
  DESCENT_STABLE: "Paracaídas desplegado · descenso estabilizado",
  LANDING: "Secuencia final de aterrizaje",
  LANDED: "Misión finalizada · beacon de recuperación activo",
};

const terrainNames = ["Verde", "Urbana", "Mixta"];

let lastState = null;
let lastPosition = null;
let totalDistanceMeters = 0;
let autoCenterMap = true;

const routeCoordinates = [];

/*
  Mapa inicial.

  Estas coordenadas coinciden con las coordenadas simuladas
  que actualmente genera app.py.
*/
const initialLatitude = -12.072;
const initialLongitude = -77.080;

const missionMap = L.map("missionMap", {
  zoomControl: true,
  attributionControl: true,
}).setView([initialLatitude, initialLongitude], 16);

/*
  Mapa base de OpenStreetMap.
*/
L.tileLayer(
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  {
    maxZoom: 19,
    attribution:
      "Tiles © Esri, Maxar, Earthstar Geographics",
  }
).addTo(missionMap);

/*
  Icono del CubeSat.
*/
const satelliteIcon = L.divIcon({
  className: "",
  html: '<div class="sirius-marker"></div>',
  iconSize: [24, 24],
  iconAnchor: [12, 12],
});

/*
  Icono del punto de lanzamiento.
*/
const launchIcon = L.divIcon({
  className: "",
  html: '<div class="launch-marker"></div>',
  iconSize: [18, 18],
  iconAnchor: [9, 9],
});

const satelliteMarker = L.marker(
  [initialLatitude, initialLongitude],
  {
    icon: satelliteIcon,
  }
)
  .addTo(missionMap)
  .bindPopup("Posición actual del CubeSat");

let launchMarker = null;

/*
  Línea que representa la trayectoria.
*/
const routeLine = L.polyline([], {
  color: "#20c7e8",
  weight: 4,
  opacity: 0.9,
}).addTo(missionMap);

const chart = new Chart($("flightChart"), {
  type: "line",

  data: {
    labels: [],

    datasets: [
      {
        label: "Altitud (m)",
        data: [],
        borderColor: "#20c7e8",
        backgroundColor: "rgba(32, 199, 232, .12)",
        tension: 0.35,
        fill: true,
        pointRadius: 0,
        yAxisID: "y",
      },
      {
        label: "Velocidad (m/s)",
        data: [],
        borderColor: "#ffd166",
        tension: 0.35,
        pointRadius: 0,
        yAxisID: "y1",
      },
    ],
  },

  options: {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,

    interaction: {
      mode: "index",
      intersect: false,
    },

    plugins: {
      legend: {
        labels: {
          color: "#c8dced",
        },
      },
    },

    scales: {
      x: {
        ticks: {
          color: "#7898b7",
          maxTicksLimit: 8,
        },

        grid: {
          color: "rgba(135,233,255,.06)",
        },
      },

      y: {
        position: "left",

        ticks: {
          color: "#7898b7",
        },

        grid: {
          color: "rgba(135,233,255,.06)",
        },
      },

      y1: {
        position: "right",

        ticks: {
          color: "#7898b7",
        },

        grid: {
          drawOnChartArea: false,
        },
      },
    },
  },
});

function formatTime(seconds) {
  const minutes = String(
    Math.floor(seconds / 60)
  ).padStart(2, "0");

  const secs = String(
    seconds % 60
  ).padStart(2, "0");

  return `${minutes}:${secs}`;
}

function addLog(message) {
  const item = document.createElement("li");

  item.textContent =
    `[${new Date().toLocaleTimeString()}] ${message}`;

  $("eventLog").prepend(item);

  while ($("eventLog").children.length > 8) {
    $("eventLog").lastChild.remove();
  }
}

function updateChart(data) {
  chart.data.labels.push(data.mission_time);

  chart.data.datasets[0].data.push(
    data.altitude
  );

  chart.data.datasets[1].data.push(
    data.vertical_velocity
  );

  if (chart.data.labels.length > 35) {
    chart.data.labels.shift();

    chart.data.datasets.forEach((dataset) => {
      dataset.data.shift();
    });
  }

  chart.update();
}

/*
  Calcula la distancia entre dos coordenadas GPS
  mediante la fórmula de Haversine.
*/
function calculateDistanceMeters(
  latitude1,
  longitude1,
  latitude2,
  longitude2
) {
  const earthRadius = 6371000;

  const toRadians = (degrees) =>
    degrees * Math.PI / 180;

  const latitudeDifference = toRadians(
    latitude2 - latitude1
  );

  const longitudeDifference = toRadians(
    longitude2 - longitude1
  );

  const a =
    Math.sin(latitudeDifference / 2) ** 2 +
    Math.cos(toRadians(latitude1)) *
      Math.cos(toRadians(latitude2)) *
      Math.sin(longitudeDifference / 2) ** 2;

  const c =
    2 * Math.atan2(
      Math.sqrt(a),
      Math.sqrt(1 - a)
    );

  return earthRadius * c;
}

function formatDistance(distanceMeters) {
  if (distanceMeters >= 1000) {
    return `${(distanceMeters / 1000).toFixed(2)} km`;
  }

  return `${distanceMeters.toFixed(1)} m`;
}

function updateMap(data) {
  const latitude = Number(data.latitude);
  const longitude = Number(data.longitude);

  if (
    !Number.isFinite(latitude) ||
    !Number.isFinite(longitude)
  ) {
    addLog("Paquete recibido sin coordenadas GPS válidas");
    return;
  }

  const currentPosition = [
    latitude,
    longitude,
  ];

  /*
    El primer punto recibido se guarda como
    punto de lanzamiento.
  */
  if (!launchMarker) {
    launchMarker = L.marker(currentPosition, {
      icon: launchIcon,
    })
      .addTo(missionMap)
      .bindPopup("Punto inicial de la misión");

    addLog("Punto inicial GPS registrado");
  }

  /*
    Evita agregar puntos prácticamente idénticos.
  */
  if (lastPosition) {
    const segmentDistance =
      calculateDistanceMeters(
        lastPosition[0],
        lastPosition[1],
        latitude,
        longitude
      );

    /*
      Solo agregamos el punto si se movió al menos
      0.5 metros.
    */
    if (segmentDistance >= 0.5) {
      totalDistanceMeters += segmentDistance;
      routeCoordinates.push(currentPosition);
      routeLine.setLatLngs(routeCoordinates);
      lastPosition = currentPosition;
    }
  } else {
    routeCoordinates.push(currentPosition);
    routeLine.setLatLngs(routeCoordinates);
    lastPosition = currentPosition;
  }

  satelliteMarker.setLatLng(currentPosition);

  satelliteMarker.setPopupContent(`
    <strong>SIRIUS CubeSat</strong><br>
    Latitud: ${latitude.toFixed(6)}<br>
    Longitud: ${longitude.toFixed(6)}<br>
    Altitud: ${data.altitude.toFixed(1)} m<br>
    Estado: ${data.mission_state}
  `);

  if (autoCenterMap) {
    missionMap.panTo(currentPosition, {
      animate: true,
      duration: 0.5,
    });
  }

  $("routePointCount").textContent =
    routeCoordinates.length;

  $("routeDistance").textContent =
    formatDistance(totalDistanceMeters);
}

function clearRoute() {
  routeCoordinates.length = 0;

  totalDistanceMeters = 0;
  lastPosition = null;

  routeLine.setLatLngs([]);

  $("routePointCount").textContent = "0";
  $("routeDistance").textContent = "0 m";

  if (launchMarker) {
    missionMap.removeLayer(launchMarker);
    launchMarker = null;
  }

  addLog("Trayectoria GPS reiniciada");
}

function centerSatellite() {
  const currentPosition =
    satelliteMarker.getLatLng();

  missionMap.setView(
    [
      currentPosition.lat,
      currentPosition.lng,
    ],
    17
  );

  autoCenterMap = true;

  addLog("Mapa centrado en el CubeSat");
}

function updateDashboard(data) {
  $("missionState").textContent =
    data.mission_state;

  $("missionMessage").textContent =
    stateMessages[data.mission_state] ||
    "Operación en curso";

  $("missionTime").textContent =
    formatTime(data.mission_time);

  $("altitude").textContent =
    `${data.altitude.toFixed(1)} m`;

  $("velocity").textContent =
    `${data.vertical_velocity.toFixed(1)} m/s`;

  $("voltage").textContent =
    `${data.voltage.toFixed(2)} V`;

  $("temperature").textContent =
    `${data.temperature.toFixed(1)} °C`;

  $("pressure").textContent =
    `${data.pressure.toFixed(1)} hPa`;

  $("packetId").textContent =
    data.packet_id;

  $("latitude").textContent =
    data.latitude.toFixed(6);

  $("longitude").textContent =
    data.longitude.toFixed(6);

  $("pitch").textContent =
    `${data.pitch.toFixed(1)}°`;

  $("roll").textContent =
    `${data.roll.toFixed(1)}°`;

  $("yaw").textContent =
    `${data.yaw.toFixed(1)}°`;

  $("greenText").textContent =
    `${data.green_percentage}%`;

  $("urbanText").textContent =
    `${data.urban_percentage}%`;

  $("mixedText").textContent =
    `${data.mixed_percentage}%`;

  $("greenBar").style.width =
    `${data.green_percentage}%`;

  $("urbanBar").style.width =
    `${data.urban_percentage}%`;

  $("mixedBar").style.width =
    `${data.mixed_percentage}%`;

  $("terrainClass").textContent =
    terrainNames[data.terrain_class] ||
    "Sin clasificar";

  $("batteryStatus").textContent =
    data.voltage < 7.2
      ? "Batería baja"
      : "Normal";

  if (lastState !== data.mission_state) {
    addLog(
      `Cambio de estado: ${data.mission_state}`
    );

    lastState = data.mission_state;
  }

  updateChart(data);
  updateMap(data);
}

async function fetchTelemetry() {
  try {
    const response = await fetch(
      "/api/telemetry/latest"
    );

    if (!response.ok) {
      throw new Error("Respuesta inválida");
    }

    const data = await response.json();

    $("connectionText").textContent =
      "Conectado";

    document.querySelector(
      ".pulse"
    ).style.background = "#44e0a1";

    updateDashboard(data);
  } catch (error) {
    $("connectionText").textContent =
      "Sin conexión";

    document.querySelector(
      ".pulse"
    ).style.background = "#ff6b6b";

    addLog(
      "No se pudo recibir telemetría del servidor"
    );

    console.error(error);
  }
}

/*
  Cuando el usuario mueve manualmente el mapa,
  dejamos de recentrarlo automáticamente.
*/
missionMap.on("dragstart", () => {
  autoCenterMap = false;
});

$("centerMapButton").addEventListener(
  "click",
  centerSatellite
);

$("clearRouteButton").addEventListener(
  "click",
  clearRoute
);

addLog("Dashboard SIRIUS iniciado");
addLog("Módulo GPS Leaflet activo");

fetchTelemetry();

setInterval(fetchTelemetry, 1000);