package com.asml.analytics.facade.client;

public final class DownstreamClientException extends RuntimeException {
    private final String downstream;

    public DownstreamClientException(String downstream, Throwable cause) {
        super("Downstream call failed: " + downstream, cause);
        this.downstream = downstream;
    }

    public String downstream() {
        return downstream;
    }
}
