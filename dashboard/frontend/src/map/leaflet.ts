// leaflet.markercluster (UMD) membutuhkan L global; modul ini dievaluasi sebelum plugin diimpor.
import L from "leaflet";
(window as unknown as { L: typeof L }).L = L;
export default L;
