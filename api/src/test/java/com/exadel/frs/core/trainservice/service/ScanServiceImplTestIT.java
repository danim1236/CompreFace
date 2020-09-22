package com.exadel.frs.core.trainservice.service;

import static com.exadel.frs.core.trainservice.service.ScanServiceImpl.MAX_FACES_TO_RECOGNIZE;
import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.when;
import com.exadel.frs.core.trainservice.dao.FaceDao;
import com.exadel.frs.core.trainservice.entity.Face;
import com.exadel.frs.core.trainservice.system.feign.python.FacesClient;
import com.exadel.frs.core.trainservice.system.feign.python.ScanResponse;
import com.exadel.frs.core.trainservice.system.feign.python.ScanResult;
import com.exadel.frs.core.trainservice.util.MultipartFileData;
import java.io.IOException;
import java.util.List;
import lombok.val;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.web.multipart.MultipartFile;

@DataJpaTest
@Import({ScanServiceImpl.class, FacesClient.class, FaceDao.class})
class ScanServiceImplTestIT {

    @Autowired
    private ScanServiceImpl scanService;

    @MockBean
    private FacesClient facesClient;

    private static final MultipartFile MULTIPART_FILE_DATA = new MultipartFileData("hex-string-1".getBytes(), "test", "application/json");
    private static final String FACE_NAME = "faceName";
    private static final String MODEL_KEY = "modelKey";
    private static final double THRESHOLD = 1.0;
    private static final double EMBEDDING = 100500;
    private static final ScanResponse SCAN_RESULT = ScanResponse.builder()
                                                                .calculatorVersion("1.0")
                                                                .result(List.of(ScanResult.builder()
                                                                                          .embedding(List.of(EMBEDDING))
                                                                                          .build()
                                                                ))
                                                                .build();

    @Test
    public void scanAndFaceTest() throws IOException {
        when(facesClient.scanFaces(MULTIPART_FILE_DATA, MAX_FACES_TO_RECOGNIZE, THRESHOLD)).thenReturn(SCAN_RESULT);

        val actual = scanService.scanAndSaveFace(MULTIPART_FILE_DATA, FACE_NAME, THRESHOLD, MODEL_KEY);

        assertThat(actual).isNotNull();
        assertThat(actual.getEmbedding()).isEqualTo(Face.Embedding.builder()
                                                                  .embeddings(SCAN_RESULT.getResult().get(0).getEmbedding())
                                                                  .calculatorVersion(SCAN_RESULT.getCalculatorVersion())
                                                                  .build()
        );
        assertThat(actual.getFaceName()).isEqualTo(FACE_NAME);
        assertThat(actual.getApiKey()).isEqualTo(MODEL_KEY);
        assertThat(actual.getApiKey()).isEqualTo(MODEL_KEY);
        assertThat(actual.getFaceImg()).isEqualTo(MULTIPART_FILE_DATA.getBytes());
        assertThat(actual.getRawImg()).isEqualTo(MULTIPART_FILE_DATA.getBytes());
    }
}