/**
 * Browser-side OpenTelemetry — traces user interactions and fetch calls,
 * exporting to the OTLP HTTP collector.
 */
import { WebTracerProvider } from "@opentelemetry/sdk-trace-web";
import { BatchSpanProcessor } from "@opentelemetry/sdk-trace-base";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-http";
import { FetchInstrumentation } from "@opentelemetry/instrumentation-fetch";
import { registerInstrumentations } from "@opentelemetry/instrumentation";
import { Resource } from "@opentelemetry/resources";
import { SEMRESATTRS_SERVICE_NAME, SEMRESATTRS_SERVICE_VERSION } from "@opentelemetry/semantic-conventions";
import { ZoneContextManager } from "@opentelemetry/context-zone";

let initialized = false;

export function initTelemetry() {
  if (initialized || typeof window === "undefined") return;
  initialized = true;

  const resource = new Resource({
    [SEMRESATTRS_SERVICE_NAME]: "pricecompare-frontend",
    [SEMRESATTRS_SERVICE_VERSION]: "1.0.0",
  });

  const exporter = new OTLPTraceExporter({
    url: process.env.NEXT_PUBLIC_OTEL_ENDPOINT || "http://localhost:4318/v1/traces",
  });

  const provider = new WebTracerProvider({ resource });
  provider.addSpanProcessor(new BatchSpanProcessor(exporter));
  provider.register({ contextManager: new ZoneContextManager() });

  registerInstrumentations({
    instrumentations: [
      new FetchInstrumentation({
        propagateTraceHeaderCorsUrls: [/localhost/, /pricecompare/],
        clearTimingResources: true,
      }),
    ],
  });
}

export function getTracer(name = "pricecompare-frontend") {
  const { trace } = require("@opentelemetry/api");
  return trace.getTracer(name);
}
