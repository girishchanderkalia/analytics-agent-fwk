package com.asml.analytics.facade.controller;
import com.asml.analytics.facade.client.DownstreamClientException;
import java.util.Map;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
@RestControllerAdvice
public class DownstreamExceptionHandler {
    @ExceptionHandler(DownstreamClientException.class)
    ResponseEntity<Map<String,Object>> handle(DownstreamClientException error) {
        return ResponseEntity.status(HttpStatus.BAD_GATEWAY).body(Map.of("code","DOWNSTREAM_ERROR","downstream",error.downstream(),"message","A downstream service call failed"));
    }
}
