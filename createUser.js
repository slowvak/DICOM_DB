    const newUser = await pb.collection("users").create({
        username: "dicom_user",
        email: "bje001@gmail.com",
        password: "DICOm123",
        passwordConfirm: "DICOm123"
    });