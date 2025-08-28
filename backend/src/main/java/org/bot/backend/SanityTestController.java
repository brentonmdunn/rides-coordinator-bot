package org.bot.backend;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class SanityTestController {

    @GetMapping("/hello")
    public String sanityTest() {
        return "Hello World";
    }

}
