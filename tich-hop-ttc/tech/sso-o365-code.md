---
title: UC-01b — Code snippets thực thi (Office 365 SSO cho GV)
scope: tich-hop-ttc
repos:
  - FE broker: ~/dev/dtp/lms-sso  (Next.js, pages router)
  - BE: ~/dev/dtp/lms-api          (Java 17, Spring Boot 3)
  - FE app: ~/dev/dtp/lms-school   (Next.js)
sources:
  - tich-hop-ttc/phan-tich-tich-hop.md §3b
  - tich-hop-ttc/tech/sso-o365-implement.md (plan)
  - tich-hop-ttc/SKILL.md §1b
status: draft
note: |
  File này tập trung 100% vào CODE THỰC THI để dev copy theo (chỉ chỉnh
  package/import cho khớp repo gốc). Phần kế hoạch + sequence + risk
  xem `sso-o365-implement.md`. Phần phân tích kiến trúc + bảng câu hỏi
  với TTC xem `phan-tich-tich-hop.md` §3b + §9.2.
---

## 0. Bản đồ file sẽ tạo / sửa

### Backend `lms-api`

```
src/main/java/vn/dtpsoft/modules/o365/
  config/
    O365OidcProperties.java
    O365WebClientConfig.java
  cache/
    OidcDiscoveryCache.java
    JwksCache.java
  client/
    O365OAuthClient.java
    O365DiscoveryDocument.java
    O365TokenResponse.java
  jwt/
    O365JwtVerifier.java
    O365Claims.java
  resolver/
    O365SsoUserResolverService.java
    ResolveResult.java
  domain/
    PendingO365User.java
    PendingO365UserRepository.java
  controller/
    O365Controller.java
    O365AdminController.java
    dto/
      O365LoginViaCodeRequest.java
      PendingO365UserDto.java
      ResolvePendingRequest.java

src/main/resources/db/changelog/changes/
  2026-05-11_user_add_o365_columns.xml
  2026-05-11_create_pending_o365_users.xml

src/main/resources/application.yml         # bổ sung block app.o365.oidc
```

### Frontend `lms-sso`

```
constants/paths.js                          # +4 paths
utils/get-server-side-props.js              # +allowedO365Sso
components/pages/CredentialLogin/
  CredentialLoginPage.js                    # +nút O365
  ThirdPartyLogin.js                        # +button "O365"
pages/o365-sso/
  index.js
  callback.js
  logout.js
  logout-callback.js
services/api/
  config.js                                 # +o365Sso block
  o365-sso.js
```

### Frontend `lms-school` (admin tool)

```
pages/admin/o365-pending/index.js
components/admin/O365Pending/
  PendingList.tsx
  MapGiaoVienModal.tsx
services/api/admin-o365.js
```

---

## 1. Backend `lms-api`

### 1.1 Maven dependency

`pom.xml`:

```xml
<dependency>
  <groupId>com.nimbusds</groupId>
  <artifactId>nimbus-jose-jwt</artifactId>
  <version>9.40</version>
</dependency>

<!-- Caffeine cho cache discovery / JWKS -->
<dependency>
  <groupId>com.github.ben-manes.caffeine</groupId>
  <artifactId>caffeine</artifactId>
</dependency>
```

> `nimbus-jose-jwt` thường đã có gián tiếp qua `spring-security-oauth2-resource-server`. Nếu module dùng Spring Security thì bỏ block trên.

### 1.2 `application.yml`

```yaml
app:
  o365:
    oidc:
      tenantId: ${O365_TENANT_ID}
      clientId: ${O365_CLIENT_ID}
      clientSecret: ${O365_CLIENT_SECRET}
      scopes: ${O365_SCOPES:openid profile email offline_access}
      discoveryUrl: https://login.microsoftonline.com/${O365_TENANT_ID}/v2.0/.well-known/openid-configuration
      allowedRedirectUris:
        - ${O365_REDIRECT_URI}
      jwt:
        clockSkewSeconds: 60
        cacheTtlHours: 24
      http:
        connectTimeoutSeconds: 5
        readTimeoutSeconds: 10
```

### 1.3 Liquibase migration

**`2026-05-11_user_add_o365_columns.xml`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<databaseChangeLog
    xmlns="http://www.liquibase.org/xml/ns/dbchangelog"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.liquibase.org/xml/ns/dbchangelog
        http://www.liquibase.org/xml/ns/dbchangelog/dbchangelog-4.7.xsd">

  <changeSet id="2026-05-11-01" author="lms-team">
    <addColumn tableName="user">
      <column name="o365_oid" type="varchar(64)"/>
      <column name="o365_tid" type="varchar(64)"/>
      <column name="upn"      type="varchar(255)"/>
    </addColumn>
  </changeSet>

  <changeSet id="2026-05-11-02" author="lms-team">
    <sql dbms="postgresql">
      CREATE UNIQUE INDEX user_idx_o365_oid_tid
        ON "user" (o365_oid, o365_tid)
        WHERE o365_oid IS NOT NULL;
    </sql>
    <sql dbms="postgresql">
      CREATE INDEX user_idx_upn ON "user" (LOWER(upn));
    </sql>
    <rollback>
      <sql>DROP INDEX IF EXISTS user_idx_o365_oid_tid;</sql>
      <sql>DROP INDEX IF EXISTS user_idx_upn;</sql>
    </rollback>
  </changeSet>
</databaseChangeLog>
```

**`2026-05-11_create_pending_o365_users.xml`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<databaseChangeLog
    xmlns="http://www.liquibase.org/xml/ns/dbchangelog"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.liquibase.org/xml/ns/dbchangelog
        http://www.liquibase.org/xml/ns/dbchangelog/dbchangelog-4.7.xsd">

  <changeSet id="2026-05-11-03" author="lms-team">
    <createTable tableName="pending_o365_users">
      <column name="id" type="bigserial">
        <constraints primaryKey="true" nullable="false"/>
      </column>
      <column name="o365_oid"     type="varchar(64)"><constraints nullable="false"/></column>
      <column name="o365_tid"     type="varchar(64)"><constraints nullable="false"/></column>
      <column name="email"        type="varchar(255)"/>
      <column name="upn"          type="varchar(255)"/>
      <column name="display_name" type="varchar(255)"/>
      <column name="first_attempted_at" type="timestamp" defaultValueComputed="NOW()">
        <constraints nullable="false"/>
      </column>
      <column name="attempted_at" type="timestamp" defaultValueComputed="NOW()">
        <constraints nullable="false"/>
      </column>
      <column name="attempt_count" type="int" defaultValueNumeric="1">
        <constraints nullable="false"/>
      </column>
      <column name="resolved_user_id" type="bigint"/>
      <column name="resolved_at"      type="timestamp"/>
      <column name="resolved_by"      type="bigint"/>
    </createTable>

    <addUniqueConstraint tableName="pending_o365_users"
                         columnNames="o365_oid, o365_tid"
                         constraintName="pending_o365_uq"/>
    <addForeignKeyConstraint baseTableName="pending_o365_users" baseColumnNames="resolved_user_id"
                             referencedTableName="user" referencedColumnNames="id"
                             constraintName="pending_o365_fk_resolved_user"/>
    <addForeignKeyConstraint baseTableName="pending_o365_users" baseColumnNames="resolved_by"
                             referencedTableName="user" referencedColumnNames="id"
                             constraintName="pending_o365_fk_resolved_by"/>

    <sql dbms="postgresql">
      CREATE INDEX pending_o365_idx_unresolved
        ON pending_o365_users (attempted_at DESC)
        WHERE resolved_user_id IS NULL;
    </sql>
  </changeSet>
</databaseChangeLog>
```

### 1.4 Config properties — `O365OidcProperties.java`

```java
package vn.dtpsoft.modules.o365.config;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;
import org.springframework.validation.annotation.Validated;

import java.util.List;

@Data
@Validated
@Component
@ConfigurationProperties(prefix = "app.o365.oidc")
public class O365OidcProperties {

    @NotBlank private String tenantId;
    @NotBlank private String clientId;
    @NotBlank private String clientSecret;
    @NotBlank private String scopes;
    @NotBlank private String discoveryUrl;
    private List<String> allowedRedirectUris = List.of();

    private Jwt  jwt  = new Jwt();
    private Http http = new Http();

    @Data public static class Jwt {
        private long clockSkewSeconds = 60;
        private long cacheTtlHours = 24;
    }

    @Data public static class Http {
        private int connectTimeoutSeconds = 5;
        private int readTimeoutSeconds = 10;
    }

    public String expectedIssuer() {
        return "https://login.microsoftonline.com/" + tenantId + "/v2.0";
    }

    public boolean isAllowedRedirectUri(String uri) {
        return uri != null && allowedRedirectUris.stream().anyMatch(uri::equals);
    }
}
```

### 1.5 WebClient — `O365WebClientConfig.java`

```java
package vn.dtpsoft.modules.o365.config;

import io.netty.channel.ChannelOption;
import io.netty.handler.timeout.ReadTimeoutHandler;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.netty.http.client.HttpClient;

import java.util.concurrent.TimeUnit;

@Configuration
public class O365WebClientConfig {

    @Bean("o365WebClient")
    public WebClient o365WebClient(O365OidcProperties props) {
        HttpClient http = HttpClient.create()
            .option(ChannelOption.CONNECT_TIMEOUT_MILLIS,
                    props.getHttp().getConnectTimeoutSeconds() * 1000)
            .doOnConnected(c -> c.addHandlerLast(new ReadTimeoutHandler(
                    props.getHttp().getReadTimeoutSeconds(), TimeUnit.SECONDS)));

        return WebClient.builder()
            .clientConnector(new ReactorClientHttpConnector(http))
            .build();
    }
}
```

### 1.6 Discovery cache — `OidcDiscoveryCache.java`

```java
package vn.dtpsoft.modules.o365.cache;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.github.benmanes.caffeine.cache.Cache;
import com.github.benmanes.caffeine.cache.Caffeine;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import vn.dtpsoft.modules.o365.config.O365OidcProperties;

import java.time.Duration;

@Slf4j
@Service
@RequiredArgsConstructor
public class OidcDiscoveryCache {

    private static final String KEY = "default";

    private final O365OidcProperties props;
    @Qualifier("o365WebClient") private final WebClient http;

    private final Cache<String, Doc> cache = Caffeine.newBuilder()
        .expireAfterWrite(Duration.ofHours(24))
        .maximumSize(1)
        .build();

    public Doc get() {
        Doc cached = cache.getIfPresent(KEY);
        if (cached != null) return cached;
        Doc fresh = fetch();
        cache.put(KEY, fresh);
        return fresh;
    }

    private Doc fetch() {
        log.info("Fetching OIDC discovery from {}", props.getDiscoveryUrl());
        Doc doc = http.get().uri(props.getDiscoveryUrl())
            .retrieve()
            .bodyToMono(Doc.class)
            .block();
        if (doc == null || doc.tokenEndpoint == null || doc.jwksUri == null) {
            throw new IllegalStateException("Invalid OIDC discovery document");
        }
        return doc;
    }

    @Data
    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class Doc {
        @JsonProperty("authorization_endpoint") private String authorizationEndpoint;
        @JsonProperty("token_endpoint")         private String tokenEndpoint;
        @JsonProperty("jwks_uri")               private String jwksUri;
        @JsonProperty("end_session_endpoint")   private String endSessionEndpoint;
        @JsonProperty("issuer")                 private String issuer;
    }
}
```

### 1.7 JWKS cache — `JwksCache.java`

```java
package vn.dtpsoft.modules.o365.cache;

import com.nimbusds.jose.jwk.JWKSet;
import com.nimbusds.jose.jwk.source.RemoteJWKSet;
import com.nimbusds.jose.proc.JWSKeySelector;
import com.nimbusds.jose.proc.JWSVerificationKeySelector;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.proc.SecurityContext;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.net.URL;
import java.util.concurrent.ConcurrentHashMap;

@Service
@RequiredArgsConstructor
public class JwksCache {

    private final OidcDiscoveryCache discovery;
    private final ConcurrentHashMap<String, JWSKeySelector<SecurityContext>> cache = new ConcurrentHashMap<>();

    public JWSKeySelector<SecurityContext> selector() {
        return cache.computeIfAbsent("default", k -> build());
    }

    private JWSKeySelector<SecurityContext> build() {
        try {
            URL jwksUrl = new URL(discovery.get().getJwksUri());
            // RemoteJWKSet TỰ refresh khi gặp `kid` chưa biết
            return new JWSVerificationKeySelector<>(
                JWSAlgorithm.RS256,
                new RemoteJWKSet<>(jwksUrl));
        } catch (Exception e) {
            throw new IllegalStateException("Cannot build JWKS selector", e);
        }
    }
}
```

### 1.8 Token exchange client — `O365OAuthClient.java`

```java
package vn.dtpsoft.modules.o365.client;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.reactive.function.BodyInserters;
import org.springframework.web.reactive.function.client.WebClient;
import vn.dtpsoft.api.exception.ApiException;
import vn.dtpsoft.api.exception.ErrorCode;
import vn.dtpsoft.modules.o365.cache.OidcDiscoveryCache;
import vn.dtpsoft.modules.o365.config.O365OidcProperties;

@Slf4j
@Service
@RequiredArgsConstructor
public class O365OAuthClient {

    private final O365OidcProperties props;
    private final OidcDiscoveryCache discovery;
    @Qualifier("o365WebClient") private final WebClient http;

    public O365TokenResponse exchangeCode(String code, String redirectUri) {
        if (!props.isAllowedRedirectUri(redirectUri)) {
            throw new ApiException(ErrorCode.O365_SSO_REDIRECT_NOT_ALLOWED);
        }

        MultiValueMap<String, String> form = new LinkedMultiValueMap<>();
        form.add("grant_type",    "authorization_code");
        form.add("code",          code);
        form.add("client_id",     props.getClientId());
        form.add("client_secret", props.getClientSecret());
        form.add("redirect_uri",  redirectUri);
        form.add("scope",         props.getScopes());

        long t0 = System.currentTimeMillis();
        try {
            return http.post()
                .uri(discovery.get().getTokenEndpoint())
                .contentType(MediaType.APPLICATION_FORM_URLENCODED)
                .body(BodyInserters.fromFormData(form))
                .retrieve()
                .bodyToMono(O365TokenResponse.class)
                .block();
        } catch (Exception e) {
            log.error("O365 token exchange failed after {}ms",
                System.currentTimeMillis() - t0, e);
            throw new ApiException(ErrorCode.O365_SSO_TOKEN_EXCHANGE_FAILED);
        }
    }
}
```

**`O365TokenResponse.java`**

```java
package vn.dtpsoft.modules.o365.client;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

@Data
@JsonIgnoreProperties(ignoreUnknown = true)
public class O365TokenResponse {
    @JsonProperty("token_type")    private String tokenType;
    @JsonProperty("scope")         private String scope;
    @JsonProperty("expires_in")    private Long   expiresIn;
    @JsonProperty("access_token")  private String accessToken;
    @JsonProperty("id_token")      private String idToken;
    @JsonProperty("refresh_token") private String refreshToken;
}
```

### 1.9 JWT verifier — `O365JwtVerifier.java` + `O365Claims.java`

```java
package vn.dtpsoft.modules.o365.jwt;

import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import com.nimbusds.jwt.proc.ConfigurableJWTProcessor;
import com.nimbusds.jwt.proc.DefaultJWTProcessor;
import com.nimbusds.jose.proc.SecurityContext;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import vn.dtpsoft.api.exception.ApiException;
import vn.dtpsoft.api.exception.ErrorCode;
import vn.dtpsoft.modules.o365.cache.JwksCache;
import vn.dtpsoft.modules.o365.config.O365OidcProperties;

import java.util.Date;

@Slf4j
@Service
@RequiredArgsConstructor
public class O365JwtVerifier {

    private final O365OidcProperties props;
    private final JwksCache jwks;

    public O365Claims verify(String idToken, String expectedNonce) {
        try {
            // 1. Parse + verify signature qua JWKS
            ConfigurableJWTProcessor<SecurityContext> p = new DefaultJWTProcessor<>();
            p.setJWSKeySelector(jwks.selector());
            JWTClaimsSet c = p.process(SignedJWT.parse(idToken), null);

            // 2. Verify iss
            String expectedIss = props.expectedIssuer();
            if (!expectedIss.equals(c.getIssuer())) {
                log.warn("O365 iss mismatch: expected={}, actual={}", expectedIss, c.getIssuer());
                throw new ApiException(ErrorCode.O365_SSO_JWT_INVALID);
            }

            // 3. Verify aud
            if (c.getAudience() == null || !c.getAudience().contains(props.getClientId())) {
                throw new ApiException(ErrorCode.O365_SSO_JWT_INVALID);
            }

            // 4. Verify tid LOCK TENANT
            String tid = (String) c.getClaim("tid");
            if (!props.getTenantId().equals(tid)) {
                log.warn("O365 tenant mismatch: expected={}, actual={}", props.getTenantId(), tid);
                throw new ApiException(ErrorCode.O365_TENANT_MISMATCH);
            }

            // 5. Verify exp / nbf với clock skew
            long now = System.currentTimeMillis();
            long skewMs = props.getJwt().getClockSkewSeconds() * 1000;
            if (c.getExpirationTime() == null || c.getExpirationTime().before(new Date(now - skewMs))) {
                throw new ApiException(ErrorCode.O365_SSO_JWT_INVALID);
            }
            if (c.getNotBeforeTime() != null
                    && c.getNotBeforeTime().after(new Date(now + skewMs))) {
                throw new ApiException(ErrorCode.O365_SSO_JWT_INVALID);
            }

            // 6. Verify nonce
            if (expectedNonce != null) {
                String nonce = (String) c.getClaim("nonce");
                if (!expectedNonce.equals(nonce)) {
                    throw new ApiException(ErrorCode.O365_SSO_NONCE_INVALID);
                }
            }

            // 7. Build domain claims
            return O365Claims.builder()
                .oid(strOrThrow(c, "oid"))
                .tid(tid)
                .email(strOrNull(c, "email"))
                .upn(strOrNull(c, "upn"))
                .preferredUsername(strOrNull(c, "preferred_username"))
                .name(strOrNull(c, "name"))
                .givenName(strOrNull(c, "given_name"))
                .familyName(strOrNull(c, "family_name"))
                .employeeId(strOrNull(c, "employeeid"))   // optional claim
                .build();
        } catch (ApiException e) {
            throw e;
        } catch (Exception e) {
            log.error("Failed to verify O365 id_token", e);
            throw new ApiException(ErrorCode.O365_SSO_JWT_INVALID);
        }
    }

    private static String strOrNull(JWTClaimsSet c, String k) {
        Object v = c.getClaim(k);
        return v == null ? null : v.toString();
    }

    private static String strOrThrow(JWTClaimsSet c, String k) {
        String v = strOrNull(c, k);
        if (v == null || v.isBlank()) throw new ApiException(ErrorCode.O365_SSO_JWT_INVALID);
        return v;
    }
}
```

```java
package vn.dtpsoft.modules.o365.jwt;

import lombok.Builder;
import lombok.Value;

@Value @Builder
public class O365Claims {
    String oid;
    String tid;
    String email;
    String upn;
    String preferredUsername;
    String name;
    String givenName;
    String familyName;
    String employeeId;

    public String resolvedEmail() {
        return email != null && !email.isBlank() ? email : preferredUsername;
    }
}
```

### 1.10 Domain — `PendingO365User` + Repository

```java
package vn.dtpsoft.modules.o365.domain;

import jakarta.persistence.*;
import lombok.*;
import java.time.Instant;

@Entity
@Table(name = "pending_o365_users")
@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class PendingO365User {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "o365_oid", nullable = false) private String o365Oid;
    @Column(name = "o365_tid", nullable = false) private String o365Tid;

    private String email;
    private String upn;
    @Column(name = "display_name") private String displayName;

    @Column(name = "first_attempted_at") private Instant firstAttemptedAt;
    @Column(name = "attempted_at")       private Instant attemptedAt;
    @Column(name = "attempt_count")      private Integer attemptCount;

    @Column(name = "resolved_user_id") private Long resolvedUserId;
    @Column(name = "resolved_at")      private Instant resolvedAt;
    @Column(name = "resolved_by")      private Long resolvedBy;
}
```

```java
package vn.dtpsoft.modules.o365.domain;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

public interface PendingO365UserRepository extends JpaRepository<PendingO365User, Long> {

    Optional<PendingO365User> findByO365OidAndO365Tid(String oid, String tid);

    @Query("SELECT p FROM PendingO365User p WHERE p.resolvedUserId IS NULL ORDER BY p.attemptedAt DESC")
    List<PendingO365User> findUnresolved();

    @Modifying
    @Query(value = """
        INSERT INTO pending_o365_users
          (o365_oid, o365_tid, email, upn, display_name)
        VALUES
          (:oid, :tid, :email, :upn, :displayName)
        ON CONFLICT (o365_oid, o365_tid) DO UPDATE SET
          attempted_at  = NOW(),
          attempt_count = pending_o365_users.attempt_count + 1,
          email         = EXCLUDED.email,
          upn           = EXCLUDED.upn,
          display_name  = EXCLUDED.display_name
        """, nativeQuery = true)
    void upsert(@Param("oid") String oid,
                @Param("tid") String tid,
                @Param("email") String email,
                @Param("upn") String upn,
                @Param("displayName") String displayName);
}
```

### 1.11 Resolver — `O365SsoUserResolverService.java`

> Giả định repo `lms-api` đã có `UserRepository`, `GiaoVienRepository` với pattern dtpsoft. Đoạn dưới minh hoạ; chỉnh method name cho khớp repo gốc.

```java
package vn.dtpsoft.modules.o365.resolver;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import vn.dtpsoft.api.exception.ApiException;
import vn.dtpsoft.api.exception.ErrorCode;
import vn.dtpsoft.modules.giaovien.domain.GiaoVien;
import vn.dtpsoft.modules.giaovien.domain.GiaoVienRepository;
import vn.dtpsoft.modules.o365.config.O365OidcProperties;
import vn.dtpsoft.modules.o365.domain.PendingO365UserRepository;
import vn.dtpsoft.modules.o365.jwt.O365Claims;
import vn.dtpsoft.modules.user.domain.User;
import vn.dtpsoft.modules.user.domain.UserRepository;
import vn.dtpsoft.modules.user.domain.UserSource;

import java.util.Optional;

@Slf4j
@Service
@RequiredArgsConstructor
public class O365SsoUserResolverService {

    private final UserRepository           userRepo;
    private final GiaoVienRepository       giaoVienRepo;
    private final PendingO365UserRepository pendingRepo;
    private final O365OidcProperties       props;

    @Transactional
    public User resolve(O365Claims c) {
        // 0. Re-check tenant lock (defence in depth)
        if (!props.getTenantId().equals(c.getTid())) {
            throw new ApiException(ErrorCode.O365_TENANT_MISMATCH);
        }

        // 1. By oid + tid
        Optional<User> u = userRepo.findByO365OidAndO365Tid(c.getOid(), c.getTid());
        if (u.isPresent()) {
            log.info("O365 resolve path=byOid oid={}", c.getOid());
            return touchProfile(u.get(), c);
        }

        // 2. By employeeId claim → GiaoVien.soDinhDanhCaNhan
        if (c.getEmployeeId() != null && !c.getEmployeeId().isBlank()) {
            Optional<GiaoVien> gv = giaoVienRepo.findBySoDinhDanhCaNhan(c.getEmployeeId());
            if (gv.isPresent()) {
                log.info("O365 resolve path=byEmployeeId employeeId={}", c.getEmployeeId());
                return linkO365ToGv(gv.get(), c);
            }
        }

        // 3. By email (case-insensitive) → GiaoVien.email, source=TTC_OPENSYNC
        String email = c.resolvedEmail();
        if (email != null && !email.isBlank()) {
            Optional<GiaoVien> gv = giaoVienRepo
                .findByEmailIgnoreCaseAndSource(email, UserSource.TTC_OPENSYNC);
            if (gv.isPresent()) {
                log.info("O365 resolve path=byEmail email={}", email);
                return linkO365ToGv(gv.get(), c);
            }
        }

        // 4. Reject + log pending
        pendingRepo.upsert(c.getOid(), c.getTid(),
                c.resolvedEmail(), c.getUpn(), c.getName());
        log.warn("O365 resolve path=pending oid={} email={}", c.getOid(), c.resolvedEmail());
        throw new ApiException(ErrorCode.TTC_SSO_USER_NOT_PROVISIONED);
    }

    private User linkO365ToGv(GiaoVien gv, O365Claims c) {
        User user = userRepo.findByGiaoVienId(gv.getId())
            .orElseThrow(() -> new ApiException(ErrorCode.TTC_SSO_USER_BRANCH_ROLE_MISSING));
        user.setO365Oid(c.getOid());
        user.setO365Tid(c.getTid());
        user.setUpn(c.getUpn());
        return touchProfile(user, c);
    }

    private User touchProfile(User user, O365Claims c) {
        if (c.resolvedEmail() != null) user.setEmail(c.resolvedEmail());
        if (c.getName() != null)       user.setFullName(c.getName());
        if (c.getGivenName() != null)  user.setFirstName(c.getGivenName());
        if (c.getFamilyName() != null) user.setLastName(c.getFamilyName());
        return userRepo.save(user);
    }
}
```

### 1.12 Controller — `O365Controller.java`

```java
package vn.dtpsoft.modules.o365.controller;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import vn.dtpsoft.api.dto.TokenAuthDto;
import vn.dtpsoft.api.exception.ApiException;
import vn.dtpsoft.api.exception.ErrorCode;
import vn.dtpsoft.modules.account.AuthService;
import vn.dtpsoft.modules.o365.client.O365OAuthClient;
import vn.dtpsoft.modules.o365.client.O365TokenResponse;
import vn.dtpsoft.modules.o365.controller.dto.O365LoginViaCodeRequest;
import vn.dtpsoft.modules.o365.jwt.O365Claims;
import vn.dtpsoft.modules.o365.jwt.O365JwtVerifier;
import vn.dtpsoft.modules.o365.resolver.O365SsoUserResolverService;
import vn.dtpsoft.modules.user.domain.User;

@Slf4j
@RestController
@RequestMapping("/o365")
@RequiredArgsConstructor
public class O365Controller {

    private final O365OAuthClient            oauth;
    private final O365JwtVerifier            verifier;
    private final O365SsoUserResolverService resolver;
    private final AuthService                auth;       // reuse: issueTokenAuth(user)

    @PostMapping("/login-via-code")
    public ResponseEntity<TokenAuthDto> loginViaCode(@RequestBody O365LoginViaCodeRequest req) {
        if (req.getCode() == null || req.getRedirectUri() == null) {
            throw new ApiException(ErrorCode.O365_SSO_CODE_INVALID);
        }

        long t0 = System.currentTimeMillis();
        O365TokenResponse token = oauth.exchangeCode(req.getCode(), req.getRedirectUri());
        if (token.getIdToken() == null) {
            throw new ApiException(ErrorCode.O365_SSO_TOKEN_EXCHANGE_FAILED);
        }

        O365Claims claims = verifier.verify(token.getIdToken(), req.getExpectedNonce());
        User user = resolver.resolve(claims);
        TokenAuthDto dto = auth.issueTokenAuth(user);

        log.info("O365 login OK userId={} elapsedMs={}", user.getId(),
                System.currentTimeMillis() - t0);
        return ResponseEntity.ok(dto);
    }
}
```

**`O365LoginViaCodeRequest.java`**

```java
package vn.dtpsoft.modules.o365.controller.dto;

import lombok.Data;

@Data
public class O365LoginViaCodeRequest {
    private String code;
    private String redirectUri;
    private String expectedNonce;
}
```

### 1.13 Admin controller — `O365AdminController.java`

```java
package vn.dtpsoft.modules.o365.controller;

import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;
import vn.dtpsoft.api.exception.ApiException;
import vn.dtpsoft.api.exception.ErrorCode;
import vn.dtpsoft.modules.o365.controller.dto.PendingO365UserDto;
import vn.dtpsoft.modules.o365.controller.dto.ResolvePendingRequest;
import vn.dtpsoft.modules.o365.domain.PendingO365User;
import vn.dtpsoft.modules.o365.domain.PendingO365UserRepository;
import vn.dtpsoft.modules.user.domain.User;
import vn.dtpsoft.modules.user.domain.UserRepository;
import vn.dtpsoft.security.SecurityUtil;

import java.time.Instant;
import java.util.List;

@RestController
@RequestMapping("/o365/pending")
@RequiredArgsConstructor
@PreAuthorize("hasAnyRole('ADMIN','SUPER_ADMIN')")
public class O365AdminController {

    private final PendingO365UserRepository pendingRepo;
    private final UserRepository            userRepo;

    @GetMapping
    public List<PendingO365UserDto> list() {
        return pendingRepo.findUnresolved().stream()
            .map(PendingO365UserDto::from)
            .toList();
    }

    @PostMapping("/{id}/resolve")
    @Transactional
    public ResponseEntity<Void> resolve(@PathVariable Long id,
                                        @RequestBody ResolvePendingRequest req) {
        PendingO365User p = pendingRepo.findById(id)
            .orElseThrow(() -> new ApiException(ErrorCode.NOT_FOUND));

        User user = userRepo.findByGiaoVienId(req.getGiaoVienId())
            .orElseThrow(() -> new ApiException(ErrorCode.NOT_FOUND));

        // 1. Set o365_oid/o365_tid lên user
        user.setO365Oid(p.getO365Oid());
        user.setO365Tid(p.getO365Tid());
        user.setUpn(p.getUpn());
        userRepo.save(user);

        // 2. Mark pending resolved
        Long adminId = SecurityUtil.currentUserId();
        p.setResolvedUserId(user.getId());
        p.setResolvedAt(Instant.now());
        p.setResolvedBy(adminId);
        pendingRepo.save(p);

        return ResponseEntity.noContent().build();
    }
}
```

**DTO**

```java
package vn.dtpsoft.modules.o365.controller.dto;

import lombok.Builder; import lombok.Value;
import vn.dtpsoft.modules.o365.domain.PendingO365User;
import java.time.Instant;

@Value @Builder
public class PendingO365UserDto {
    Long id;
    String email;
    String upn;
    String displayName;
    Instant firstAttemptedAt;
    Instant attemptedAt;
    Integer attemptCount;

    public static PendingO365UserDto from(PendingO365User p) {
        return PendingO365UserDto.builder()
            .id(p.getId())
            .email(p.getEmail())
            .upn(p.getUpn())
            .displayName(p.getDisplayName())
            .firstAttemptedAt(p.getFirstAttemptedAt())
            .attemptedAt(p.getAttemptedAt())
            .attemptCount(p.getAttemptCount())
            .build();
    }
}
```

```java
package vn.dtpsoft.modules.o365.controller.dto;

import lombok.Data;

@Data
public class ResolvePendingRequest {
    private Long giaoVienId;
}
```

### 1.14 Error codes bổ sung

Trong file `ErrorCode.java` (enum chung):

```java
public enum ErrorCode {
    // ... existing ...
    O365_SSO_CODE_INVALID            ("O365_SSO_CODE_INVALID",            400),
    O365_SSO_REDIRECT_NOT_ALLOWED    ("O365_SSO_REDIRECT_NOT_ALLOWED",    400),
    O365_SSO_TOKEN_EXCHANGE_FAILED   ("O365_SSO_TOKEN_EXCHANGE_FAILED",   502),
    O365_SSO_JWT_INVALID             ("O365_SSO_JWT_INVALID",             401),
    O365_SSO_NONCE_INVALID           ("O365_SSO_NONCE_INVALID",           401),
    O365_TENANT_MISMATCH             ("O365_TENANT_MISMATCH",             401),
    TTC_SSO_USER_NOT_PROVISIONED     ("TTC_SSO_USER_NOT_PROVISIONED",     403),
    TTC_SSO_USER_BRANCH_ROLE_MISSING ("TTC_SSO_USER_BRANCH_ROLE_MISSING", 403);
    // ...
}
```

---

## 2. Frontend `lms-sso` (Next.js, pages router)

### 2.1 `constants/paths.js` — thêm

```js
export const paths = {
  // ... existing
  o365Sso: "/o365-sso",
  o365SsoCallback: "/o365-sso/callback",
  o365SsoLogout: "/o365-sso/logout",
  o365SsoLogoutCallback: "/o365-sso/logout-callback",
};

export const unauthenticatedPaths = [
  // ... existing
  paths.o365Sso,
  paths.o365SsoCallback,
  paths.o365SsoLogout,
  paths.o365SsoLogoutCallback,
];
```

### 2.2 Helper `utils/o365.js`

```js
import crypto from "crypto";

export const O365_AUTHORIZE_URL = (tenantId) =>
  `https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/authorize`;

export const O365_LOGOUT_URL = (tenantId) =>
  `https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/logout`;

export const randomToken = () => crypto.randomBytes(16).toString("hex");

export const buildAuthorizeUrl = ({
  tenantId, clientId, redirectUri, scope, state, nonce,
}) => {
  const url = new URL(O365_AUTHORIZE_URL(tenantId));
  url.searchParams.set("client_id", clientId);
  url.searchParams.set("response_type", "code");
  url.searchParams.set("redirect_uri", redirectUri);
  url.searchParams.set("scope", scope);
  url.searchParams.set("response_mode", "query");
  url.searchParams.set("state", state);
  url.searchParams.set("nonce", nonce);
  url.searchParams.set("prompt", "select_account");
  return url.toString();
};
```

### 2.3 `pages/o365-sso/index.js` (entry)

```js
import { paths } from "@/constants/paths";
import { buildAuthorizeUrl, randomToken } from "@/utils/o365";

const COOKIE_TTL_SEC = 600;

export async function getServerSideProps(ctx) {
  const { req, res, query } = ctx;

  if (!process.env.O365_TENANT_ID || !process.env.O365_CLIENT_ID) {
    return { redirect: { destination: "/sign-in?error=o365-config", permanent: false } };
  }

  // Optional: feature flag theo host
  const enabledHosts = (process.env.HOSTS_ENABLE_O365_SSO || "").split(",").filter(Boolean);
  const host = req.headers.host || "";
  if (enabledHosts.length > 0 && !enabledHosts.includes(host)) {
    return { redirect: { destination: "/sign-in", permanent: false } };
  }

  const state = randomToken();
  const nonce = randomToken();
  const cookieOpts = `Path=/; HttpOnly; SameSite=Lax; Max-Age=${COOKIE_TTL_SEC}` +
                     (process.env.NODE_ENV === "production" ? "; Secure" : "");
  res.setHeader("Set-Cookie", [
    `o365_sso_state=${state}; ${cookieOpts}`,
    `o365_sso_nonce=${nonce}; ${cookieOpts}`,
  ]);

  const origin = (process.env.PUBLIC_ORIGIN || `https://${host}`).replace(/\/$/, "");
  const redirectUri = `${origin}${paths.o365SsoCallback}`;

  const url = buildAuthorizeUrl({
    tenantId:    process.env.O365_TENANT_ID,
    clientId:    process.env.O365_CLIENT_ID,
    redirectUri,
    scope:       process.env.O365_SCOPES || "openid profile email offline_access",
    state, nonce,
  });

  return { redirect: { destination: url, permanent: false } };
}

export default function O365SsoEntry() { return null; }
```

### 2.4 `pages/o365-sso/callback.js`

```js
import { paths } from "@/constants/paths";
import { setAllAuthCookies } from "@/utils/cookies";
import { createDestinationUrl } from "@/utils/destination";
import { parse as parseCookie } from "cookie";
import { o365SsoApi } from "@/services/api/o365-sso";

export async function getServerSideProps(ctx) {
  const { req, res, query } = ctx;
  const cookies = parseCookie(req.headers.cookie || "");

  const { code, state, error: oauthError } = query;
  if (oauthError) {
    return redirect(`/sign-in?error=o365-${oauthError}`);
  }
  if (!code || !state) return redirect("/sign-in?error=o365-sso");
  if (state !== cookies.o365_sso_state) return redirect("/sign-in?error=o365-state");

  const host = req.headers.host || "";
  const origin = (process.env.PUBLIC_ORIGIN || `https://${host}`).replace(/\/$/, "");
  const redirectUri = `${origin}${paths.o365SsoCallback}`;

  let auth;
  try {
    auth = await o365SsoApi.loginViaCode({
      code,
      redirectUri,
      expectedNonce: cookies.o365_sso_nonce,
    });
  } catch (e) {
    const code = e?.response?.data?.code || "o365-sso";
    return redirect(`/sign-in?error=${code.toLowerCase()}`);
  }

  // Clear ephemeral cookies
  res.setHeader("Set-Cookie", [
    `o365_sso_state=; Path=/; HttpOnly; Max-Age=0`,
    `o365_sso_nonce=; Path=/; HttpOnly; Max-Age=0`,
  ]);
  setAllAuthCookies(res, auth);

  const dest = createDestinationUrl({
    roleCode:    auth.userRole,
    branchId:    auth.branchId,
    destination: auth.lmsSiteUrl,
  });
  return { redirect: { destination: dest, permanent: false } };
}

const redirect = (destination) => ({ redirect: { destination, permanent: false } });

export default function O365SsoCallback() { return null; }
```

### 2.5 `pages/o365-sso/logout.js`

```js
import { paths } from "@/constants/paths";
import { clearAllAuthCookies, getAuthCookies } from "@/utils/cookies";
import { randomToken, O365_LOGOUT_URL } from "@/utils/o365";

export async function getServerSideProps(ctx) {
  const { req, res } = ctx;
  const { idToken } = getAuthCookies(req);
  const state = randomToken();

  res.setHeader("Set-Cookie", [
    `o365_logout_state=${state}; Path=/; HttpOnly; SameSite=Lax; Max-Age=600` +
    (process.env.NODE_ENV === "production" ? "; Secure" : ""),
  ]);
  clearAllAuthCookies(res);

  const host = req.headers.host || "";
  const origin = (process.env.PUBLIC_ORIGIN || `https://${host}`).replace(/\/$/, "");

  const url = new URL(O365_LOGOUT_URL(process.env.O365_TENANT_ID));
  url.searchParams.set("post_logout_redirect_uri", `${origin}${paths.o365SsoLogoutCallback}`);
  if (idToken) url.searchParams.set("id_token_hint", idToken);
  url.searchParams.set("state", state);

  return { redirect: { destination: url.toString(), permanent: false } };
}

export default function O365SsoLogout() { return null; }
```

### 2.6 `pages/o365-sso/logout-callback.js`

```js
import { parse as parseCookie } from "cookie";

export async function getServerSideProps(ctx) {
  const { req, res, query } = ctx;
  const cookies = parseCookie(req.headers.cookie || "");
  res.setHeader("Set-Cookie", `o365_logout_state=; Path=/; HttpOnly; Max-Age=0`);

  if (query.state && query.state !== cookies.o365_logout_state) {
    return { redirect: { destination: "/sign-in?error=o365-logout-state", permanent: false } };
  }
  return { redirect: { destination: "/sign-in", permanent: false } };
}

export default function O365SsoLogoutCallback() { return null; }
```

### 2.7 `services/api/config.js` — thêm

```js
export const apiConfig = {
  // ... existing
  o365Sso: {
    loginViaCode: { url: "/o365/login-via-code", method: "POST" },
  },
};
```

### 2.8 `services/api/o365-sso.js`

```js
import axios from "axios";
import { apiConfig } from "./config";

const client = axios.create({
  baseURL: process.env.LMS_API_BASE_URL,
  timeout: 15000,
});

export const o365SsoApi = {
  loginViaCode: async (body) => {
    const cfg = apiConfig.o365Sso.loginViaCode;
    const resp = await client.request({ url: cfg.url, method: cfg.method, data: body });
    return resp.data;
  },
};
```

### 2.9 Nút "Đăng nhập với Office 365" — `ThirdPartyLogin.js`

```jsx
import Link from "next/link";
import { paths } from "@/constants/paths";

export function ThirdPartyLogin({ enableO365Sso, enableTtcSso }) {
  return (
    <div className="flex flex-col gap-2 mt-4">
      {enableO365Sso && (
        <Link href={paths.o365Sso}
              className="flex items-center justify-center gap-2 border rounded px-4 py-2 hover:bg-gray-50">
          <MicrosoftLogo className="w-5 h-5" />
          Đăng nhập với Office 365
        </Link>
      )}
      {enableTtcSso && (
        <Link href={paths.ttcSso}
              className="flex items-center justify-center gap-2 border rounded px-4 py-2 hover:bg-gray-50">
          Đăng nhập với TTC
        </Link>
      )}
    </div>
  );
}

function MicrosoftLogo({ className = "" }) {
  return (
    <svg viewBox="0 0 23 23" className={className} aria-hidden>
      <rect width="10" height="10" x="1"  y="1"  fill="#F25022"/>
      <rect width="10" height="10" x="12" y="1"  fill="#7FBA00"/>
      <rect width="10" height="10" x="1"  y="12" fill="#00A4EF"/>
      <rect width="10" height="10" x="12" y="12" fill="#FFB900"/>
    </svg>
  );
}
```

`CredentialLoginPage.js` — gọi `<ThirdPartyLogin enableO365Sso={allowedO365Sso} enableTtcSso={allowedTtcSso} />`.

---

## 3. Frontend `lms-school` — Admin tool

### 3.1 `services/api/admin-o365.js`

```js
import axios from "axios";

const api = axios.create({ baseURL: process.env.NEXT_PUBLIC_LMS_API_BASE_URL });

export const adminO365 = {
  listPending: () => api.get("/o365/pending").then(r => r.data),
  resolve:     (id, giaoVienId) =>
    api.post(`/o365/pending/${id}/resolve`, { giaoVienId }),
};
```

### 3.2 `pages/admin/o365-pending/index.js`

```jsx
import { useEffect, useState } from "react";
import { adminO365 } from "@/services/api/admin-o365";
import MapGiaoVienModal from "@/components/admin/O365Pending/MapGiaoVienModal";

export default function O365PendingPage() {
  const [items, setItems] = useState([]);
  const [picked, setPicked] = useState(null);
  const reload = () => adminO365.listPending().then(setItems);

  useEffect(() => { reload(); }, []);

  return (
    <div className="p-6">
      <h1 className="text-xl font-semibold mb-4">Pending O365 Users</h1>
      <table className="w-full text-sm border">
        <thead className="bg-gray-100">
          <tr>
            <th className="p-2 text-left">Email</th>
            <th className="p-2 text-left">UPN</th>
            <th className="p-2 text-left">Tên hiển thị</th>
            <th className="p-2 text-left">Lần đầu thử</th>
            <th className="p-2 text-left">Lần gần nhất</th>
            <th className="p-2 text-right">Số lần</th>
            <th className="p-2"></th>
          </tr>
        </thead>
        <tbody>
          {items.map(p => (
            <tr key={p.id} className="border-t">
              <td className="p-2">{p.email}</td>
              <td className="p-2">{p.upn}</td>
              <td className="p-2">{p.displayName}</td>
              <td className="p-2">{new Date(p.firstAttemptedAt).toLocaleString()}</td>
              <td className="p-2">{new Date(p.attemptedAt).toLocaleString()}</td>
              <td className="p-2 text-right">{p.attemptCount}</td>
              <td className="p-2">
                <button className="px-3 py-1 bg-blue-600 text-white rounded"
                        onClick={() => setPicked(p)}>Map vào GV</button>
              </td>
            </tr>
          ))}
          {items.length === 0 && (
            <tr><td colSpan={7} className="p-4 text-center text-gray-500">
              Không có pending request.
            </td></tr>
          )}
        </tbody>
      </table>

      {picked && (
        <MapGiaoVienModal pending={picked}
                          onClose={() => setPicked(null)}
                          onResolved={() => { setPicked(null); reload(); }} />
      )}
    </div>
  );
}
```

### 3.3 `components/admin/O365Pending/MapGiaoVienModal.tsx`

```tsx
import { useState } from "react";
import { adminO365 } from "@/services/api/admin-o365";
import { searchGiaoVien } from "@/services/api/giao-vien";  // pre-existing

export default function MapGiaoVienModal({ pending, onClose, onResolved }) {
  const [q, setQ] = useState(pending?.email || "");
  const [matches, setMatches] = useState([]);
  const [loading, setLoading] = useState(false);

  const onSearch = async () => {
    setLoading(true);
    try { setMatches(await searchGiaoVien({ q })); }
    finally { setLoading(false); }
  };

  const onPick = async (gv) => {
    if (!confirm(`Map ${pending.email} → ${gv.hoTen} (${gv.soDinhDanhCaNhan})?`)) return;
    await adminO365.resolve(pending.id, gv.id);
    onResolved();
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center">
      <div className="bg-white rounded p-6 w-[640px]">
        <h2 className="font-semibold mb-2">Map vào Giáo viên</h2>
        <p className="text-sm text-gray-600 mb-3">
          Email O365: <b>{pending.email}</b> · UPN: <b>{pending.upn}</b>
        </p>
        <div className="flex gap-2 mb-3">
          <input className="border flex-1 px-3 py-2 rounded"
                 value={q} onChange={e => setQ(e.target.value)}
                 placeholder="Tìm theo CCCD / email / họ tên" />
          <button className="px-3 py-2 bg-gray-700 text-white rounded" onClick={onSearch}>
            {loading ? "..." : "Tìm"}
          </button>
        </div>
        <ul className="max-h-64 overflow-auto divide-y">
          {matches.map(gv => (
            <li key={gv.id} className="py-2 flex justify-between items-center">
              <span>
                {gv.hoTen}
                <span className="text-gray-500 text-xs ml-2">
                  {gv.soDinhDanhCaNhan} · {gv.email}
                </span>
              </span>
              <button className="px-3 py-1 bg-blue-600 text-white rounded"
                      onClick={() => onPick(gv)}>Chọn</button>
            </li>
          ))}
        </ul>
        <div className="text-right mt-4">
          <button className="px-3 py-2 border rounded" onClick={onClose}>Đóng</button>
        </div>
      </div>
    </div>
  );
}
```

---

## 4. Test snippets

### 4.1 Unit — `O365JwtVerifierTest.java`

```java
package vn.dtpsoft.modules.o365.jwt;

import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.RSASSASigner;
import com.nimbusds.jose.jwk.RSAKey;
import com.nimbusds.jose.jwk.gen.RSAKeyGenerator;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import org.junit.jupiter.api.Test;
import vn.dtpsoft.api.exception.ApiException;
import vn.dtpsoft.api.exception.ErrorCode;

import java.util.Date;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class O365JwtVerifierTest {

    private static final String TENANT = "11111111-2222-3333-4444-555555555555";
    private static final String CLIENT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";

    @Test
    void rejects_wrong_tenant() throws Exception {
        var rsa = new RSAKeyGenerator(2048).keyID("kid-1").generate();
        var jwt = signedJwt(rsa, JWTClaimsSet.parse("""
            {
              "iss": "https://login.microsoftonline.com/%s/v2.0",
              "aud": "%s",
              "tid": "WRONG-TENANT",
              "oid": "user-1",
              "exp": %d
            }
            """.formatted(TENANT, CLIENT, (System.currentTimeMillis() + 60000) / 1000)));

        var verifier = buildVerifier(rsa);
        ApiException ex = assertThrows(ApiException.class, () -> verifier.verify(jwt, null));
        assertEquals(ErrorCode.O365_TENANT_MISMATCH, ex.getCode());
    }

    @Test
    void rejects_wrong_audience() throws Exception { /* similar */ }
    @Test void rejects_expired() throws Exception { /* similar */ }
    @Test void accepts_valid() throws Exception { /* similar */ }

    private String signedJwt(RSAKey rsa, JWTClaimsSet claims) throws Exception {
        var jwt = new SignedJWT(
            new JWSHeader.Builder(JWSAlgorithm.RS256).keyID(rsa.getKeyID()).build(),
            claims);
        jwt.sign(new RSASSASigner(rsa));
        return jwt.serialize();
    }

    private O365JwtVerifier buildVerifier(RSAKey rsa) {
        // Wire props + custom JwksCache returning rsa.toPublicJWK()
        // (omitted — implement với in-memory ImmutableJWKSet)
        return null;
    }
}
```

### 4.2 Integration — `O365ControllerIT` (sketch)

```java
@SpringBootTest
@AutoConfigureMockMvc
class O365ControllerIT {

    @Autowired MockMvc mvc;
    @MockBean O365OAuthClient oauth;
    @MockBean O365JwtVerifier verifier;
    @Autowired O365SsoUserResolverService resolver;

    @Test
    void rejects_when_redirect_uri_not_whitelisted() throws Exception {
        when(oauth.exchangeCode(any(), eq("https://evil.example/cb")))
            .thenThrow(new ApiException(ErrorCode.O365_SSO_REDIRECT_NOT_ALLOWED));

        mvc.perform(post("/o365/login-via-code")
            .contentType(MediaType.APPLICATION_JSON)
            .content("""
              { "code": "abc", "redirectUri": "https://evil.example/cb" }
              """))
            .andExpect(status().isBadRequest());
    }
}
```

### 4.3 FE — `pages/o365-sso/__tests__/callback.test.js`

```js
import { getServerSideProps } from "@/pages/o365-sso/callback";

jest.mock("@/services/api/o365-sso", () => ({
  o365SsoApi: { loginViaCode: jest.fn() },
}));

test("redirect to /sign-in when state mismatch", async () => {
  const ctx = {
    req: { headers: { cookie: "o365_sso_state=AAA; o365_sso_nonce=NNN" } },
    res: { setHeader: jest.fn() },
    query: { code: "X", state: "BBB" },
  };
  const out = await getServerSideProps(ctx);
  expect(out.redirect.destination).toMatch(/error=o365-state/);
});
```

---

## 5. Thứ tự build (1 dev full-stack)

| Bước | File | Validate |
|------|------|----------|
| 1 | Liquibase 2 changeset | `liquibase update` thành công; cột `o365_*` xuất hiện |
| 2 | `O365OidcProperties` + `application.yml` + `O365WebClientConfig` | App khởi động không lỗi với env giả lập |
| 3 | `OidcDiscoveryCache` + `JwksCache` | Call discovery thật với env TTC IT cấp, log thấy hit/miss |
| 4 | `O365OAuthClient` + `O365TokenResponse` | Curl test exchange code (Postman) thấy id_token |
| 5 | `O365JwtVerifier` + `O365Claims` + **unit test** | Toàn bộ 4 case verifier pass |
| 6 | `PendingO365User` + Repository + native upsert | Insert 2 lần cùng `(oid,tid)` → `attempt_count=2` |
| 7 | `O365SsoUserResolverService` | Unit test 4 path: byOid / byEmployeeId / byEmail / pending |
| 8 | `O365Controller` + DTO + ErrorCode entries | Postman E2E với JWT mock được |
| 9 | FE `lms-sso` paths + entry + callback | Browser flow → callback nhận code, gọi BE thành công |
| 10 | FE button + i18n | UX hiển thị nút đúng host |
| 11 | FE logout + logout callback | Browser flow → Microsoft logout → quay lại /sign-in |
| 12 | `O365AdminController` + admin page `lms-school` | Admin map pending → user login lại byOid OK |
| 13 | Pen-test state/nonce/tid + load test exchange | Báo cáo go-live |

> Mỗi bước có thể `git commit` riêng để rollback dễ. Step 1–8 backend trước; step 9–11 frontend đi song song khi backend đã có endpoint ổn.

---

## 6. Lưu ý quan trọng (gotcha)

1. **`employeeid` viết thường** trong claim Entra (kể cả khi cấu hình `employeeId` trong Token configuration). Code đang đọc `c.getClaim("employeeid")` — KHÔNG đổi sang camelCase.
2. **`tid` claim có thể null** nếu admin Entra quên bật `tid` trong optional claims hoặc dùng v1 token. Verifier hiện trả `O365_TENANT_MISMATCH` cho cả 2 case — đủ an toàn.
3. **`aud` claim** trong v2 token là `client_id` (GUID); trong v1 là URI app. Code đang giả định v2 — đảm bảo discoveryUrl trỏ tới `/v2.0`.
4. **`RemoteJWKSet` của nimbus tự refresh** khi gặp `kid` chưa biết — không cần cache JWKS thủ công cho lifetime ngắn.
5. **Cookie `o365_sso_nonce`** phải đọc được ở callback page — đặt `Path=/`, không `Path=/o365-sso` (vì callback cũng nằm dưới `/o365-sso` nhưng SameSite=Lax cần Path đủ rộng nếu callback dùng third-party redirect).
6. **`prompt=select_account`** cần thiết khi user đã login O365 ở tab khác — không có thì Entra trả thẳng token của user cũ, dễ gây nhầm tài khoản khi GV dùng chung máy.
7. **`refresh_token`** Entra trả về **BIND vào scope `offline_access`** — nếu LMS muốn dùng để gia hạn session, phải đảm bảo scope này có trong cả authorize lẫn token request.
8. **Encoding URL param `scope`**: dấu cách trong scope (`openid profile email`) phải là `%20` chứ KHÔNG phải `+` — `URL.searchParams.set` của Node tự encode đúng.

---

*Cập nhật khi: TTC IT cấp env thật → smoke test pass; hoặc khi pattern dtpsoft thay đổi (vd repo dùng `R2dbcTemplate` thay JPA).*
